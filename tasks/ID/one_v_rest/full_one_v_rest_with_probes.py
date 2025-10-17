# full_one_v_rest_with_probes.py
import pyControl.utility as pc
from hardware_definition import right_port, left_port, center_port, final_valve, odor_A, odor_B, thermistor_sync, speaker

#----------------------------VARIABLES TO EDIT------------------------------------
pc.v.required_center_hold_duration = 300
pc.v.n_allowed_rwds = 200
# --- NEW: Probe controls ---
pc.v.probe_probability = 0.15   # e.g., 0.10 = 10% of trials are probe trials
# Put the manifold channel numbers here for your probe odors (assumes odor_B manifold).
# If probes live on a different manifold, swap odor_B.* calls in _choose_probe_for_this_trial()
pc.v.probe_valves = [6, 7,9,10,11,12]     
#---------------------------------------------------------------------------------

# =======================
# ===== CONFIG ==========
# =======================

# Tone: plays while center LED is ON
TONE_FREQ_1 = 4500  # Hz

# Non-target odors (B options) — EDIT to match Teensy manifold mapping.
# One of these channels is chosen at random on RIGHT-rewarded trials during ITI.
pc.v.non_target_odors = [2, 3, 4, 5]
pc.v.current_odor = None       # 'A', 'B', 'P' (probe), or None (to de-duplicate serial prints)
pc.v.B_current_valve = None    # chosen per trial when B is used
pc.v.P_current_valve = None    # chosen per probe trial

# Reward sizing
pc.v.reward_duration_multiplier = 0.75
pc.v.choice_window_ms = 5000

# Shaping / timing
pc.v.early_error_buffer_duration   = 300     # ms grace after entering wait_for_center_poke
pc.v.odor_delivery_duration        = 500     # ms final valve ON before choice
pc.v.final_valve_flush_duration    = 500     # ms TTL close delay to flush

# Session / ITI / timeouts
pc.v.session_duration = 1 * pc.hour
pc.v.reward_durations = [47, 54]  # [left, right] ms
pc.v.ITI_duration     = 3 * pc.second
pc.v.timeout_duration = 2 * pc.second        # generic default; will be overridden below as needed
pc.v.timeout_early_ms = 500                  # penalty for EARLY side pokes (during wait_for_center_poke)
pc.v.timeout_wrong_ms = 2000                 # penalty for WRONG choice after valid center hold

# Bias correction (ON by default here)
pc.v.bias_correction = False
pc.v.p_left          = 0.5
pc.v.max_side_prob   = 0.75
pc.v.bias_step       = 0.01
pc.v.bias_window     = 20
pc.v.choice_hist     = []

# Stats / trackers
pc.v.entry_time          = 0
pc.v.n_total_trials      = 0            # includes probe trials
pc.v.n_task_trials       = 0            # excludes early errors & probe trials (for accuracy)
pc.v.n_probe_trials      = 0
pc.v.n_early_errors      = 0
pc.v.mov_ave_correct     = 0
pc.v.overall_ave_correct = 0
pc.v.choice              = "right"
pc.v.rewarded_side       = "left" if (pc.random() > 0.5) else "right"
pc.v.outcome             = 0
pc.v.n_correct_trials    = 0
pc.v.n_rewards           = 0
pc.v.ave_correct_tracker = pc.OnlineMovingAverage(10)

# Trial type
pc.v.is_probe_trial      = False
pc.v.trial_type          = "task"       # 'task' or 'probe'

# =======================
# ===== ODOR LOGIC ======
# =======================

def _choose_B_for_this_trial_if_needed():
    if pc.v.B_current_valve is None:
        pc.v.B_current_valve = pc.choice(pc.v.non_target_odors)
        odor_B.set_valve(pc.v.B_current_valve)

def _choose_probe_for_this_trial():
    # Choose which probe valve to use this trial and set the manifold
    pc.v.P_current_valve = pc.choice(pc.v.probe_valves)
    odor_B.set_valve(pc.v.P_current_valve)

# A = left (fixed), B = right (random among non_target_odors), P = probe (from probe_valves)
def set_odor_valves():
    if pc.v.is_probe_trial:
        _choose_probe_for_this_trial()
        # Ensure only B manifold is ON for probe
        if pc.v.current_odor != 'P':
            if pc.v.current_odor == 'A':
                odor_A.off()
            elif pc.v.current_odor == 'B':
                odor_B.off()
            odor_B.on()
            pc.v.current_odor = 'P'
        return

    # Task (non-probe) trials:
    if pc.v.rewarded_side == "left":
        if pc.v.current_odor != 'A':
            if pc.v.current_odor == 'B' or pc.v.current_odor == 'P':
                odor_B.off()
            odor_A.on()
            pc.v.current_odor = 'A'
    else:  # right
        _choose_B_for_this_trial_if_needed()
        if pc.v.current_odor != 'B':
            if pc.v.current_odor == 'A' or pc.v.current_odor == 'P':
                odor_A.off()
            odor_B.on()
            pc.v.current_odor = 'B'

def disable_odor_valves():
    if pc.v.current_odor == 'A':
        odor_A.off()
    elif pc.v.current_odor in ('B', 'P'):
        odor_B.off()
    pc.v.current_odor = None

# ===========================
# ===== TRIAL SELECTION =====
# ===========================

def _record_choice_for_bias():
    # Do not adapt bias using probe trials
    if pc.v.is_probe_trial:
        return
    ch = 'L' if pc.v.choice == 'left' else ('R' if pc.v.choice == 'right' else None)
    if ch:
        pc.v.choice_hist.append(ch)
        if len(pc.v.choice_hist) > pc.v.bias_window:
            pc.v.choice_hist.pop(0)

def _update_side_probability():
    n = len(pc.v.choice_hist)
    if n < 5:
        # Not enough history; drift toward 0.5
        if pc.v.p_left > 0.5:
            pc.v.p_left = max(0.5, pc.v.p_left - 0.02)
        elif pc.v.p_left < 0.5:
            pc.v.p_left = min(0.5, pc.v.p_left + 0.02)
        return

    left_count = sum(1 for c in pc.v.choice_hist if c == 'L')
    left_frac  = left_count / n
    neutral_low, neutral_high = 0.45, 0.55

    if left_frac > neutral_high:
        pc.v.p_left = max(1.0 - pc.v.max_side_prob, pc.v.p_left - pc.v.bias_step)  # >= 0.25
    elif left_frac < neutral_low:
        pc.v.p_left = min(pc.v.max_side_prob, pc.v.p_left + pc.v.bias_step)        # <= 0.75
    else:
        # drift gently toward 0.5
        if pc.v.p_left > 0.5:
            pc.v.p_left = max(0.5, pc.v.p_left - 0.02)
        elif pc.v.p_left < 0.5:
            pc.v.p_left = min(0.5, pc.v.p_left + 0.02)

def _choose_trial_type_and_side():
    # Decide if probe or task trial
    pc.v.is_probe_trial = pc.withprob(pc.v.probe_probability)
    pc.v.trial_type = "probe" if pc.v.is_probe_trial else "task"

    if not pc.v.is_probe_trial:
        # Decide rewarded side (with / without bias correction)
        if pc.v.bias_correction:
            _update_side_probability()
            pc.v.rewarded_side = "left" if pc.withprob(pc.v.p_left) else "right"
        else:
            pc.v.rewarded_side = "left" if pc.withprob(0.5) else "right"

    # Reset per-trial valve choices
    pc.v.B_current_valve = None
    pc.v.P_current_valve = None

def is_rewarded(side):
    pc.v.choice = side
    if pc.v.is_probe_trial:
        # No rewards on probe trials; leave outcome as 0 and do not update accuracy counters here
        pc.v.outcome = 0
        return 0

    # Task trial logic
    if side == pc.v.rewarded_side:
        pc.v.n_correct_trials += 1
        pc.v.n_rewards += 1
        pc.v.outcome = 1
    else:
        pc.v.outcome = 0
    pc.v.ave_correct_tracker.add(pc.v.outcome)
    return pc.v.outcome

def do_other_ITI_logic():
    _record_choice_for_bias()
    _choose_trial_type_and_side()
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
    "center_poke", "right_poke", "left_poke",
    "center_poke_out", "right_poke_out", "left_poke_out",
    "session_timer", "finish_ITI",
    "close_final_valve", "close_final_valve_done",
    "center_poke_held",
    "set_odor_valves_for_trial", "therm_sync_ON",
    "choice_window_over", "svf_recheck"
]

initial_state = "wait_for_center_poke"

# =======================
# ===== RUN HOOKS  ======
# =======================

def run_start():
    pc.set_timer("session_timer", pc.v.session_duration)
    pc.publish_event("set_odor_valves_for_trial")

def run_end():
    right_port.SOL.off()
    left_port.SOL.off()
    center_port.LED.off()
    disable_odor_valves()
    speaker.off()
    pc.print("SESSION_DONE")

# =======================
# ===== HELPERS    ======
# =======================

def _rwd_ms(side_index):
    # Ensure integer ms for timers
    return int(pc.v.reward_duration_multiplier * pc.v.reward_durations[side_index])

# State-independent behaviour.
def all_states(event):
    if event == "session_timer":
        pc.stop_framework()

    elif event == "close_final_valve":
        final_valve.off()

    # After new trial's odor is selected in ITI, set valves once final valve is definitely closed.
    elif event == "set_odor_valves_for_trial":
        if pc.timer_remaining("close_final_valve_done") == 0:
            set_odor_valves()
        else:
            pc.set_timer("svf_recheck", 50)

    elif event == "svf_recheck":
        if pc.timer_remaining("close_final_valve_done") == 0:
            set_odor_valves()
        else:
            pc.reset_timer("svf_recheck", 50)

# =======================
# ===== STATES      =====
# =======================

def wait_for_center_poke(event):

    if event == "entry":
        center_port.LED.on()
        speaker.sine(TONE_FREQ_1)
        pc.v.entry_time = pc.get_current_time()

    elif (
        ((pc.get_current_time() - pc.v.entry_time) > pc.v.early_error_buffer_duration)
        and (event == "left_poke" or event == "right_poke")
    ):
        center_port.LED.off()
        speaker.off()
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
        speaker.off()
        final_valve.on()
        pc.timed_goto_state("wait_for_side_poke", pc.v.odor_delivery_duration)

    elif event == "exit":
        disable_odor_valves()
        pc.set_timer("close_final_valve", pc.v.final_valve_flush_duration)
        pc.set_timer("close_final_valve_done", pc.v.final_valve_flush_duration + 200)

def wait_for_side_poke(event):
    if event == "entry":
        if pc.v.choice_window_ms > 0:
            pc.set_timer("choice_window_over", pc.v.choice_window_ms)

    # --- Probe trials: any side poke ends the trial without reward or timeout ---
    if pc.v.is_probe_trial:
        if event == "left_poke" or event == "right_poke":
            pc.v.choice = "left" if event == "left_poke" else "right"
            # Do not update accuracy stats for probe trials
            pc.goto_state("inter_trial_interval")
        elif event == "choice_window_over":
            # No side poke during window; just proceed to ITI (no accuracy update)
            pc.goto_state("inter_trial_interval")
        return

    # --- Task trials (rewarded side) ---
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

        # Tally trial counts
        pc.v.n_total_trials += 1
        if pc.v.is_probe_trial:
            pc.v.n_probe_trials += 1
        else:
            # Only task trials (non-probe, excluding early errors which were already handled)
            pc.v.n_task_trials += 1

        # Accuracy metrics (task trials only)
        pc.v.mov_ave_correct = pc.v.ave_correct_tracker.ave
        denom = max(pc.v.n_task_trials, 1)
        pc.v.overall_ave_correct = pc.v.n_correct_trials / denom

        # Minimal telemetry
        pc.print_variables([
            "n_total_trials", "n_task_trials", "n_probe_trials", "n_correct_trials", "n_early_errors",
            "mov_ave_correct", "overall_ave_correct",
            "trial_type", "rewarded_side", "choice", "outcome", "p_left",
            "B_current_valve", "P_current_valve"
        ])

        # Decide next trial and pre-set odor once safe.
        do_other_ITI_logic()

    # Optional: extend ITI if still licking rewarded spout in the first half (task trials only)
    elif (
        (not pc.v.is_probe_trial)
        and pc.v.outcome
        and (
            ((event == "left_poke") and pc.v.choice == "left")
            or ((event == "right_poke") and pc.v.choice == "right")
        )
        and ((pc.get_current_time() - pc.v.entry_time) < (pc.v.ITI_duration / 2))
    ):
        pc.reset_timer("finish_ITI", pc.v.ITI_duration)

    elif event == "finish_ITI":
        pc.goto_state("wait_for_center_poke")

    elif event == "exit":
        if pc.v.n_rewards >= pc.v.n_allowed_rwds:
            pc.stop_framework()
