# full_one_v_rest.py
#
# One-vs-rest odor discrimination with bias correction.
#
# UPDATED for new hardware definition + Option B:
#   - Manifold valves via set_odor_valves()/enable_odor_valves()/disable_odor_valves()
#   - Final valve via final_on()/final_off() (serial #OLF:a / #OLF:x)
#   - Do NOT prefill next manifold until final valve is confirmed closed (post-flush)
#   - Acquisition sync beacons run continuously via start_acq_pulses()/stop_acq_pulses()
#
# Trial structure:
#   ITI selects rewarded side + odor identity
#   -> when safe (final valve closed) prefill manifold for next trial
#   center hold -> final_on() delivers odor
#   odor end -> disable_odor_valves() (manifold off)
#   flush end -> final_off()

import pyControl.utility as pc
from hardware_definition import (
    right_port, left_port, center_port,  rwd_durations,
    # New odor framework:
    set_odor_valves, enable_odor_valves, disable_odor_valves,
    final_on, final_off,
    # Acquisition sync beacons:
    start_acq_pulses, stop_acq_pulses, handle_acq_pulse_events, ACQ_SYNC_EVENT
)

# ---------------------------- VARIABLES TO EDIT --------------------------------
pc.v.required_center_hold_duration = 300
pc.v.n_allowed_rwds = 240
pc.v.bias_correction = True   # True to enable adaptive side probabilities
# -------------------------------------------------------------------------------

# =======================
# ===== CONFIG ==========
# =======================

# Odor table: name / manifold valve / rewarded side.
# For one-vs-rest:
#   - A (valve 1) is LEFT-rewarded (target)
#   - B1–B4 (valves 2–5) are RIGHT-rewarded (rest)
pc.v.odors = [
    {"name": "A",  "valve": 1, "side": "left"},
    {"name": "B", "valve": 2, "side": "right"},
    {"name": "C", "valve": 3, "side": "right"},
    {"name": "D", "valve": 4, "side": "right"},
    {"name": "E", "valve": 5, "side": "right"},
]

pc.v.current_odor       = None   # dict from pc.v.odors
pc.v.current_valve      = None   # int valve number
pc.v.current_odor_name  = ""     # convenience for logging

# Reward sizing
pc.v.reward_duration_multiplier = 1
pc.v.choice_window_ms           = 5000

# Shaping / timing
pc.v.early_error_buffer_duration = 300    # ms grace after entering wait_for_center_poke
pc.v.odor_delivery_duration      = 500    # ms final valve ON before choice
pc.v.final_valve_flush_duration  = 1000   # ms final stays ON after manifold is closed

# Session / ITI / timeouts
pc.v.session_duration = 1 * pc.hour
pc.v.reward_durations = rwd_durations     # [left, right] ms
pc.v.ITI_duration     = 3 * pc.second     # must exceed final_valve_flush_duration
pc.v.timeout_duration = 2 * pc.second     # generic default; overridden as needed
pc.v.timeout_early_ms = 500               # penalty for EARLY side pokes
pc.v.timeout_wrong_ms = 2000              # penalty for WRONG choice

# Bias correction
pc.v.p_left        = 0.5      # current probability to schedule a LEFT-rewarded trial
pc.v.max_side_prob = 0.75     # cap either side to 0.75 (min becomes 0.25)
pc.v.bias_step     = 0.01     # step size when adapting p_left
pc.v.bias_window   = 20       # number of recent trials to estimate bias over
pc.v.choice_hist   = []       # rolling list of 'L'/'R' choices (<= bias_window)

# Stats / trackers
pc.v.entry_time          = 0
pc.v.n_total_trials      = 0
pc.v.n_early_errors      = 0
pc.v.mov_ave_correct     = 0
pc.v.overall_ave_correct = 0
pc.v.choice              = "right"
pc.v.rewarded_side       = "left" if (pc.random() > 0.5) else "right"
pc.v.outcome             = 0
pc.v.n_correct_trials    = 0
pc.v.n_rewards           = 0
pc.v.ave_correct_tracker = pc.OnlineMovingAverage(10)

# Option B gating flag (don’t prefill until final valve confirmed closed)
pc.v.odor_preset_done = False


# =======================
# ===== ODOR LOGIC ======
# =======================

def _odors_for_side(side):
    return [o for o in pc.v.odors if o["side"] == side]

def choose_odor_for_rewarded_side():
    """
    Given pc.v.rewarded_side ('left' or 'right'), choose a specific odor
    instance from pc.v.odors with that side and store it in pc.v.current_odor.
    """
    candidates = _odors_for_side(pc.v.rewarded_side)
    if not candidates:
        pc.v.current_odor = None
        pc.v.current_valve = None
        pc.v.current_odor_name = ""
        return

    pc.v.current_odor = pc.choice(candidates)
    pc.v.current_valve = int(pc.v.current_odor["valve"])
    pc.v.current_odor_name = pc.v.current_odor["name"]

def _set_manifold_for_current_trial():
    """
    Prefill manifold for the selected trial odor.
    IMPORTANT: called only when Option B gate says it’s safe.
    """
    if pc.v.current_valve is None:
        return
    set_odor_valves(pc.v.current_valve)
    enable_odor_valves()


# =======================
# ===== BIAS LOGIC  =====
# =======================

def _record_choice_for_bias():
    # store last choice in rolling window, if it’s L/R
    if pc.v.choice in ("left", "right"):
        pc.v.choice_hist.append("L" if pc.v.choice == "left" else "R")
        if len(pc.v.choice_hist) > pc.v.bias_window:
            pc.v.choice_hist = pc.v.choice_hist[-pc.v.bias_window:]

def _update_side_probability():
    # If animal is biased to one side, schedule more of the opposite.
    # Example: if too many R choices, increase p_left.
    if len(pc.v.choice_hist) < 5:
        return

    frac_left = pc.v.choice_hist.count("L") / len(pc.v.choice_hist)
    # Want frac_left ~ 0.5; error positive means too many left choices.
    err = frac_left - 0.5
    pc.v.p_left = pc.v.p_left - err * pc.v.bias_step

    # Clamp
    lo = 1.0 - pc.v.max_side_prob
    hi = pc.v.max_side_prob
    if pc.v.p_left < lo:
        pc.v.p_left = lo
    if pc.v.p_left > hi:
        pc.v.p_left = hi

def check_update_rewarded_side():
    if pc.v.bias_correction:
        _update_side_probability()
        pc.v.rewarded_side = "left" if pc.withprob(pc.v.p_left) else "right"
    else:
        pc.v.rewarded_side = "left" if pc.withprob(0.5) else "right"

    # Once side is chosen, pick a specific odor for that side.
    choose_odor_for_rewarded_side()
    return

def is_rewarded(side):
    pc.v.choice = side
    if side == pc.v.rewarded_side:
        pc.v.n_correct_trials += 1
        pc.v.n_rewards += 1
        pc.v.outcome = 1
    else:
        pc.v.outcome = 0
    pc.v.ave_correct_tracker.add(pc.v.outcome)
    return pc.v.outcome

def _rwd_ms(side_index):
    return int(pc.v.reward_duration_multiplier * pc.v.reward_durations[side_index])

def do_other_ITI_logic():
    # Update bias tracking based on last trial
    _record_choice_for_bias()

    # Decide next rewarded side + select a specific odor
    check_update_rewarded_side()

    # Ask all_states() to apply odor valves when safe (Option B)
    pc.publish_event("set_odor_valves_for_trial")


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

    # valve gating / option B
    "close_final_valve", "close_final_valve_done",
    "set_odor_valves_for_trial", "svf_recheck",

    # acquisition beacons (sync)
    ACQ_SYNC_EVENT,
]

initial_state = "wait_for_center_poke"


# =======================
# ===== RUN HOOKS  ======
# =======================

def run_start():
    # Safety: ensure final valve closed at start
    final_off()
    disable_odor_valves()

    # Start acquisition beacons (independent of odors)
    start_acq_pulses()

    pc.v.odor_preset_done = False
    pc.set_timer("session_timer", pc.v.session_duration)

    # Decide first trial and request odor preset when safe.
    do_other_ITI_logic()

def run_end():
    # Stop acquisition beacons
    stop_acq_pulses()

    right_port.SOL.off()
    left_port.SOL.off()
    center_port.LED.off()

    # shut down odor plumbing
    disable_odor_valves()
    final_off()

    pc.print("SESSION_DONE")


# =======================
# ===== ALL STATES  =====
# =======================

def all_states(event):
    # Drive acquisition beacons
    handle_acq_pulse_events(event)

    if event == "session_timer":
        pc.stop_framework()

    elif event == "close_final_valve":
        final_off()

    # Option B: only prefill manifold once the final valve is definitely closed.
    elif event == "set_odor_valves_for_trial":
        if pc.timer_remaining("close_final_valve_done") == 0 and not pc.v.odor_preset_done:
            _set_manifold_for_current_trial()
            pc.v.odor_preset_done = True
        elif not pc.v.odor_preset_done:
            pc.set_timer("svf_recheck", 50)

    elif event == "svf_recheck":
        if pc.timer_remaining("close_final_valve_done") == 0 and not pc.v.odor_preset_done:
            _set_manifold_for_current_trial()
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
        # Early side poke -> timeout
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

        # Deliver odor to animal: open final valve
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
        # No choice made
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
        denom = max(pc.v.n_total_trials - pc.v.n_early_errors, 1)
        pc.v.overall_ave_correct = pc.v.n_correct_trials / denom

        pc.print_variables([
            "n_total_trials", "n_correct_trials", "n_early_errors",
            "mov_ave_correct", "overall_ave_correct",
            "rewarded_side", "current_odor_name", "choice", "outcome",
            "p_left"
        ])

        # Stop session if reward cap reached
        if pc.v.n_rewards >= pc.v.n_allowed_rwds:
            pc.stop_framework()
            return

        # Decide next trial and request odor preset when safe.
        pc.v.odor_preset_done = False
        do_other_ITI_logic()

    elif event == "finish_ITI":
        pc.goto_state("wait_for_center_poke")
