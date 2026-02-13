# odor_blocks_2.py

import pyControl.utility as pc
from hardware_definition import (
    right_port, left_port, center_port, rwd_durations,
    # odor plumbing (new framework)
    set_odor_valves, enable_odor_valves, disable_odor_valves,
    final_on, final_off,
    # acquisition sync (independent of odor timing)
    start_acq_pulses, stop_acq_pulses, handle_acq_pulse_events, ACQ_SYNC_EVENT
)

# =======================
# ===== CONFIG ==========
# =======================

# ---------------------------- VARIABLES TO EDIT --------------------------------
pc.v.n_allowed_rwds = 200  # total per session (assuming a 5uL reward size)
pc.v.required_center_hold_duration = 200
# -------------------------------------------------------------------------------

# Tone frequency (plays whenever center LED is ON) - optional


# Mapping:
#   - "A" is always the LEFT-rewarded odor class (fixed valve 1 by default).
#   - "B" is always the RIGHT-rewarded odor class (randomly chosen from non_target_odors).
pc.v.A_valve = 1
pc.v.non_target_odors = [2, 3, 4]  # EDIT to match your manifold mapping

# Reward sizing
pc.v.reward_duration_multiplier = 1
pc.v.choice_window_ms = 5000

# Odor timing
pc.v.odor_delivery_duration = 500          # ms final valve ON before side choice
pc.v.final_valve_flush_duration = 1000     # ms final valve remains ON after manifold is closed
pc.v.ITI_duration = 3 * pc.second          # must exceed final_valve_flush_duration

# Session / timeouts
pc.v.session_duration = 1 * pc.hour
pc.v.reward_durations = rwd_durations      # [left, right] ms from hardware definition
pc.v.timeout_duration = 2 * pc.second
pc.v.timeout_early_ms = 500
pc.v.timeout_wrong_ms = 2000
pc.v.early_error_buffer_duration = 300

# Rewards-per-block function (keep your shaping schedule here)
def get_n_rwds_allowed_in_block():
    pc.v.n_allowed_rwds_per_block = 3

# Block counters
pc.v.n_allowed_rwds_per_block = 3
pc.v.n_rewards_in_block = 0

# =======================
# ===== STATE VARS ======
# =======================

pc.v.entry_time = 0

pc.v.n_total_trials = 0
pc.v.n_early_errors = 0
pc.v.mov_ave_correct = 0
pc.v.overall_ave_correct = 0

pc.v.choice = "right"
pc.v.outcome = 0
pc.v.n_correct_trials = 0
pc.v.n_rewards = 0
pc.v.ave_correct_tracker = pc.OnlineMovingAverage(10)

# Trial identity
pc.v.rewarded_side = "left" if (pc.random() > 0.5) else "right"  # block starts left or right
pc.v.current_valve = None      # int
pc.v.current_odor_name = ""    # "A" or "B<number>" (for logging)
pc.v.B_current_valve = None    # int chosen for the current B trial

# Option B safety gate: only preset odor when final valve is definitely closed.
pc.v.odor_preset_done = False


# =======================
# ===== ODOR LOGIC ======
# =======================

def _choose_B_for_this_trial_if_needed():
    if pc.v.B_current_valve is None:
        pc.v.B_current_valve = pc.choice(pc.v.non_target_odors)

def choose_valve_for_this_trial():
    """
    Sets pc.v.current_valve and pc.v.current_odor_name based on pc.v.rewarded_side.
    Does NOT actuate hardware.
    """
    if pc.v.rewarded_side == "left":
        pc.v.current_valve = int(pc.v.A_valve)
        pc.v.current_odor_name = "A"
    else:
        _choose_B_for_this_trial_if_needed()
        pc.v.current_valve = int(pc.v.B_current_valve)
        pc.v.current_odor_name = f"B{pc.v.current_valve}"

def preset_odor_valves_for_trial():
    """
    OPTION B: called only when the final valve is confirmed closed.
    Opens the manifold for the upcoming trial.
    """
    if pc.v.current_valve is None:
        return
    set_odor_valves(pc.v.current_valve)
    enable_odor_valves()

def stop_manifold_for_trial():
    """Close manifold for current trial (odor line OFF)."""
    disable_odor_valves()


# ============ Reward-side / block helpers ============

def do_other_ITI_logic():
    # Prepare next trial's reward side by block logic
    check_update_rewarded_side()
    # Reset B choice so the next right-rewarded trial picks a fresh non-target
    pc.v.B_current_valve = None
    # Pick the specific valve for this trial (A fixed; B random)
    choose_valve_for_this_trial()
    # Ask the all_states handler to apply valves once it's safe (Option B gate)
    pc.publish_event("set_odor_valves_for_trial")

def check_update_rewarded_side():
    # A always means left; B always means right.
    if pc.v.n_rewards_in_block >= pc.v.n_allowed_rwds_per_block:
        pc.v.rewarded_side = "left" if (pc.v.rewarded_side == "right") else "right"
        get_n_rwds_allowed_in_block()
        pc.v.n_rewards_in_block = 0
    return

def is_rewarded(side):
    pc.v.choice = side
    if side == pc.v.rewarded_side:
        pc.v.n_correct_trials += 1
        pc.v.n_rewards_in_block += 1
        pc.v.n_rewards += 1
        pc.v.outcome = 1
    else:
        pc.v.outcome = 0
    pc.v.ave_correct_tracker.add(pc.v.outcome)
    return pc.v.outcome

def _rwd_ms(side_index):
    return int(pc.v.reward_duration_multiplier * pc.v.reward_durations[side_index])


# =======================
# ===== STATE SETUP =====
# =======================

states = [
    "wait_for_center_poke",
    "deliver_odor",
    "wait_for_side_poke",
    "left_reward",
    "right_reward",
    "inter_trial_interval",
    "timeout",
]

events = [
    # pokes
    "center_poke", "right_poke", "left_poke",
    "center_poke_out", "right_poke_out", "left_poke_out",

    # timers / framework
    "session_timer", "finish_ITI",
    "center_poke_held",
    "choice_window_over",

    # valve gating
    "close_final_valve", "close_final_valve_done",
    "set_odor_valves_for_trial", "svf_recheck",

    # acquisition beacon (sync only)
    ACQ_SYNC_EVENT,
]

initial_state = "wait_for_center_poke"


# =======================
# ===== RUN HOOKS  ======
# =======================

def run_start():
    # Make sure final valve is closed at session start.
    final_off()

    # Start acquisition beacons (independent of odor timing).
    start_acq_pulses()

    pc.v.odor_preset_done = False
    pc.set_timer("session_timer", pc.v.session_duration)

    # Choose first trial and request valve preset once safe.
    do_other_ITI_logic()

def run_end():
    stop_acq_pulses()

    right_port.SOL.off()
    left_port.SOL.off()
    center_port.LED.off()

    # shut down odor plumbing (safe)
    stop_manifold_for_trial()
    final_off()

    pc.print("SESSION_DONE")


# =======================
# ===== ALL STATES  =====
# =======================

def all_states(event):
    # Drive the acquisition beacons (sync pulses) regardless of state.
    handle_acq_pulse_events(event)

    if event == "session_timer":
        pc.stop_framework()

    elif event == "close_final_valve":
        final_off()

    # OPTION B: only preset the next trial odor once final valve is definitely closed.
    elif event == "set_odor_valves_for_trial":
        if pc.timer_remaining("close_final_valve_done") == 0 and not pc.v.odor_preset_done:
            preset_odor_valves_for_trial()
            pc.v.odor_preset_done = True
        elif not pc.v.odor_preset_done:
            pc.set_timer("svf_recheck", 50)

    elif event == "svf_recheck":
        if pc.timer_remaining("close_final_valve_done") == 0 and not pc.v.odor_preset_done:
            preset_odor_valves_for_trial()
            pc.v.odor_preset_done = True
        elif not pc.v.odor_preset_done:
            pc.reset_timer("svf_recheck", 50)


# =======================
# ===== STATES      =====
# =======================

def wait_for_center_poke(event):

    if event == "entry":
        center_port.LED.on()
        # speaker.sine(TONE_FREQ_1)  # optional
        pc.v.entry_time = pc.get_current_time()

    elif (
        ((pc.get_current_time() - pc.v.entry_time) > pc.v.early_error_buffer_duration)
        and (event == "left_poke" or event == "right_poke")
    ):
        center_port.LED.off()
        # speaker.off()  # optional
        # Early side poke: treat as early error and time out.
        stop_manifold_for_trial()
        pc.v.n_early_errors += 1
        pc.v.timeout_duration = pc.v.timeout_early_ms
        pc.goto_state("timeout")

    elif (event == "left_poke_out" or event == "right_poke_out"):
        pc.v.entry_time = pc.get_current_time()

    elif event == "center_poke":
        pc.set_timer("center_poke_held", pc.v.required_center_hold_duration)

    elif event == "center_poke_out":
        pc.disarm_timer("center_poke_held")

    elif event == "center_poke_held":
        pc.goto_state("deliver_odor")


def deliver_odor(event):
    if event == "entry":
        center_port.LED.off()
        # speaker.off()  # optional

        # Deliver odor to animal by opening final valve.
        # (Manifold should already be preset/open from ITI once safe.)
        final_on()

        pc.timed_goto_state("wait_for_side_poke", pc.v.odor_delivery_duration)

    elif event == "exit":
        # End of odor exposure: manifold off FIRST, then flush, then final off.
        stop_manifold_for_trial()

        pc.set_timer("close_final_valve", pc.v.final_valve_flush_duration)
        pc.set_timer("close_final_valve_done", pc.v.final_valve_flush_duration + 200)


def wait_for_side_poke(event):
    if event == "entry":
        if pc.v.choice_window_ms > 0:
            pc.set_timer("choice_window_over", pc.v.choice_window_ms)

    if event == "right_poke":
        if is_rewarded("right"):
            pc.goto_state("right_reward")
        else:
            pc.v.timeout_duration = pc.v.timeout_wrong_ms
            pc.goto_state("timeout")

    elif event == "left_poke":
        if is_rewarded("left"):
            pc.goto_state("left_reward")
        else:
            pc.v.timeout_duration = pc.v.timeout_wrong_ms
            pc.goto_state("timeout")

    elif event == "choice_window_over":
        pc.v.outcome = 0
        pc.v.ave_correct_tracker.add(0)
        pc.goto_state("inter_trial_interval")


def left_reward(event):
    if event == "entry":
        left_port.SOL.on()
        pc.timed_goto_state("inter_trial_interval", _rwd_ms(0))
    elif event == "exit":
        left_port.SOL.off()


def right_reward(event):
    if event == "entry":
        right_port.SOL.on()
        pc.timed_goto_state("inter_trial_interval", _rwd_ms(1))
    elif event == "exit":
        right_port.SOL.off()


def timeout(event):
    if event == "entry":
        pc.timed_goto_state("inter_trial_interval", pc.v.timeout_duration)


def inter_trial_interval(event):
    if event == "entry":
        pc.set_timer("finish_ITI", pc.v.ITI_duration)
        pc.v.entry_time = pc.get_current_time()

        # Update stats
        pc.v.n_total_trials += 1
        pc.v.mov_ave_correct = pc.v.ave_correct_tracker.ave
        pc.v.overall_ave_correct = pc.v.n_correct_trials / max(pc.v.n_total_trials - pc.v.n_early_errors, 1)

        pc.print_variables([
            "n_total_trials", "n_correct_trials", "n_early_errors",
            "mov_ave_correct", "overall_ave_correct",
            "rewarded_side", "current_odor_name", "choice", "outcome"
        ])

        # Decide next trial + request odor preset (Option B gate applies).
        pc.v.odor_preset_done = False
        do_other_ITI_logic()

    elif event == "finish_ITI":
        pc.goto_state("wait_for_center_poke")

    elif event == "exit":
        if pc.v.n_rewards >= pc.v.n_allowed_rwds:
            pc.stop_framework()
