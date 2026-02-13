

import pyControl.utility as pc
from hardware_definition import (
    right_port, left_port, center_port, rwd_durations,
    # Odor plumbing:
    set_odor_valves, enable_odor_valves, disable_odor_valves,
    final_on, final_off,
    # Acquisition sync beacons:
    start_acq_pulses, stop_acq_pulses, handle_acq_pulse_events, ACQ_SYNC_EVENT,
)

# ---------------------------- VARIABLES TO EDIT -------------------------------
pc.v.required_center_hold_duration = 300
pc.v.n_allowed_rwds = 250

# Map your manifold valve numbers here:
pc.v.left_rewarded_valves  = [1, 2]   # 2 odors rewarded on LEFT
pc.v.right_rewarded_valves = [3, 4]   # 2 odors rewarded on RIGHT
# -----------------------------------------------------------------------------

# =======================
# ===== CONFIG ==========
# =======================

pc.v.choice_window_ms            = 5000
pc.v.odor_delivery_duration      = 500      # ms final valve ON before choice
pc.v.final_valve_flush_duration  = 1000     # ms final stays ON after manifold is closed
pc.v.session_duration            = 1 * pc.hour
pc.v.reward_durations            = rwd_durations  # [left, right] ms
pc.v.ITI_duration                = 3 * pc.second
pc.v.timeout_early_ms            = 500
pc.v.timeout_wrong_ms            = 2000
pc.v.early_error_buffer_duration = 300

# =======================
# ===== VARIABLES =======
# =======================

pc.v.entry_time        = 0
pc.v.n_total_trials    = 0
pc.v.n_early_errors    = 0
pc.v.n_correct_trials  = 0
pc.v.n_rewards         = 0
pc.v.choice            = "none"
pc.v.rewarded_side     = "right"

pc.v.current_valve     = None   # manifold valve number for this trial
pc.v.current_odor_name = ""     # for logging ("L1", "L2", "R3", etc.)
pc.v.odor_preset_done  = False  # Option B gating flag
pc.v.outcome           = 0


# =======================
# ===== ODOR LOGIC ======
# =======================

def _validate_valve_lists():
    if not pc.v.left_rewarded_valves or not pc.v.right_rewarded_valves:
        raise Exception("left_rewarded_valves and right_rewarded_valves must be non-empty lists.")
    # Ensure they are ints
    pc.v.left_rewarded_valves = [int(v) for v in pc.v.left_rewarded_valves]
    pc.v.right_rewarded_valves = [int(v) for v in pc.v.right_rewarded_valves]

def select_next_trial():
    """
    Randomly choose one of the 4 odors uniformly:
      - 2 from left_rewarded_valves -> rewarded_side = 'left'
      - 2 from right_rewarded_valves -> rewarded_side = 'right'
    Then request manifold prefill once safe (Option B).
    """
    all_choices = (
        [("left", v) for v in pc.v.left_rewarded_valves] +
        [("right", v) for v in pc.v.right_rewarded_valves]
    )
    side, valve = pc.choice(all_choices)

    pc.v.rewarded_side = side
    pc.v.current_valve = int(valve)
    pc.v.current_odor_name = ("L" if side == "left" else "R") + str(pc.v.current_valve)

    # Trigger Option B prefill attempt (all_states will gate it)
    pc.publish_event("set_odor_valves_for_trial")

def preset_odor_for_trial():
    """
    OPTION B: called only once final valve is confirmed closed.
    Opens the manifold valve for the upcoming trial.
    """
    if pc.v.current_valve is None:
        return
    set_odor_valves(pc.v.current_valve)
    enable_odor_valves()

def clear_trial_odor_state():
    """Close manifold valves and clear odor identity."""
    disable_odor_valves()
    pc.v.current_valve = None
    pc.v.current_odor_name = ""

def is_rewarded(side):
    pc.v.choice = side
    correct = (side == pc.v.rewarded_side)
    pc.v.outcome = 1 if correct else 0
    if correct:
        pc.v.n_correct_trials += 1
        pc.v.n_rewards += 1
    return correct

def _rwd_ms(side_index):
    return int(pc.v.reward_durations[side_index])


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
    "close_final_valve", "close_final_valve_done",
    "center_poke_held",
    "choice_window_over",

    # Option B gating
    "set_odor_valves_for_trial",
    "svf_recheck",

    # acquisition beacon (sync only)
    ACQ_SYNC_EVENT,
]

initial_state = "wait_for_center_poke"


# =======================
# ===== RUN HOOKS  ======
# =======================

def run_start():
    _validate_valve_lists()

    # Safety on start
    final_off()
    disable_odor_valves()

    # Start acquisition beacons (independent of odor timing)
    start_acq_pulses()

    pc.v.odor_preset_done = False
    pc.set_timer("session_timer", pc.v.session_duration)

    # Select first trial
    select_next_trial()

def run_end():
    stop_acq_pulses()

    right_port.SOL.off()
    left_port.SOL.off()
    center_port.LED.off()

    clear_trial_odor_state()
    final_off()

    pc.print("SESSION_DONE")


# =======================
# ===== ALL STATES  =====
# =======================

def all_states(event):
    # Drive acquisition beacon pulses
    handle_acq_pulse_events(event)

    if event == "session_timer":
        pc.stop_framework()

    elif event == "close_final_valve":
        final_off()

    # Option B: prefill manifold only once final valve is definitely closed.
    elif event == "set_odor_valves_for_trial":
        if pc.timer_remaining("close_final_valve_done") == 0 and not pc.v.odor_preset_done:
            preset_odor_for_trial()
            pc.v.odor_preset_done = True
        elif not pc.v.odor_preset_done:
            pc.set_timer("svf_recheck", 50)

    elif event == "svf_recheck":
        if pc.timer_remaining("close_final_valve_done") == 0 and not pc.v.odor_preset_done:
            preset_odor_for_trial()
            pc.v.odor_preset_done = True
        elif not pc.v.odor_preset_done:
            pc.reset_timer("svf_recheck", 50)


# =======================
# ===== STATES      =====
# =======================

def wait_for_center_poke(event):
    if event == "entry":
        center_port.LED.on()
        pc.v.entry_time = pc.get_current_time()

    elif (
        ((pc.get_current_time() - pc.v.entry_time) > pc.v.early_error_buffer_duration)
        and (event == "left_poke" or event == "right_poke")
    ):
        # Early side poke
        center_port.LED.off()
        disable_odor_valves()
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

        # Deliver odor to animal: open final valve (manifold should already be open)
        final_on()
        pc.timed_goto_state("wait_for_side_poke", pc.v.odor_delivery_duration)

    elif event == "exit":
        # End odor exposure: close manifold first, then flush, then close final
        disable_odor_valves()
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

        pc.v.n_total_trials += 1
        pc.print_variables([
            "n_total_trials", "n_correct_trials", "n_early_errors",
            "rewarded_side", "current_odor_name", "choice", "outcome"
        ])

        if pc.v.n_rewards >= pc.v.n_allowed_rwds:
            pc.stop_framework()
            return

        pc.v.odor_preset_done = False
        select_next_trial()

    elif event == "finish_ITI":
        pc.goto_state("wait_for_center_poke")
