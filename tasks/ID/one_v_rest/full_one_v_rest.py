import pyControl.utility as pc
from hardware_definition import right_port, left_port, center_port, final_valve, odor_A, odor_B, thermistor_sync

# =======================
# ===== CONFIG ==========
# =======================

# Reward sizing
# For rwd durn multplier of 1, 1 mL ~ 225 rew
pc.v.reward_duration_multiplier = 1
pc.v.n_allowed_rwds = 180  # total per session

# ---- Bias correction (OFF by default) ----
pc.v.bias_correction = False   # Set True to enable adaptive side probabilities
pc.v.p_left          = 0.5     # Current probability to schedule a LEFT-rewarded trial
pc.v.max_side_prob   = 0.75    # Upper cap for either side (lower cap is 1 - max = 0.25)
pc.v.bias_step       = 0.05    # How quickly to adapt per ITI step
pc.v.bias_window     = 20      # Number of recent trials to assess bias
pc.v.choice_hist     = []      # Rolling list of 'L'/'R' choices (length <= bias_window)

# =======================
# ===== ODOR LOGIC ======
# =======================

def set_odor_valves():
    # A -> left; B -> right (odor_B's channel is selected elsewhere in your pipeline)
    if pc.v.rewarded_side == "left":
        odor_B.off()
        odor_A.on()
    elif pc.v.rewarded_side == "right":
        odor_A.off()
        odor_B.on()

def disable_odor_valves():
    odor_A.off()
    odor_B.off()

### Helper functions for rewards / trial prep ###

def do_other_ITI_logic():
    check_update_rewarded_side()
    pc.publish_event("set_odor_valves_for_trial")

# --- Bias adaptation helpers ---

def _record_choice_for_bias():
    # Append the last trial's CHOICE into a rolling window for bias estimation.
    ch = None
    if pc.v.choice == 'left':
        ch = 'L'
    elif pc.v.choice == 'right':
        ch = 'R'
    if ch:
        pc.v.choice_hist.append(ch)
        if len(pc.v.choice_hist) > pc.v.bias_window:
            # drop oldest
            pc.v.choice_hist.pop(0)

def _update_side_probability():
    # Adjust pc.v.p_left based on recent choice bias.
    # Compute left fraction over the recent window; if too left-heavy, nudge p_left down, etc.
    n = len(pc.v.choice_hist)
    if n < 5:
        # Not enough history; slowly relax toward 0.5
        if pc.v.p_left > 0.5:
            pc.v.p_left = max(0.5, pc.v.p_left - 0.02)
        elif pc.v.p_left < 0.5:
            pc.v.p_left = min(0.5, pc.v.p_left + 0.02)
        return

    left_count = sum(1 for c in pc.v.choice_hist if c == 'L')
    left_frac  = left_count / n

    # Define a neutral band; only adapt outside it.
    neutral_low, neutral_high = 0.45, 0.55

    if left_frac > neutral_high:
        # Animal is choosing LEFT more than balanced -> schedule fewer LEFT-rewarded trials
        pc.v.p_left = max(1.0 - pc.v.max_side_prob, pc.v.p_left - pc.v.bias_step)  # >= 0.25
    elif left_frac < neutral_low:
        # Animal is choosing RIGHT more than balanced -> schedule more LEFT-rewarded trials
        pc.v.p_left = min(pc.v.max_side_prob, pc.v.p_left + pc.v.bias_step)        # <= 0.75
    else:
        # In neutral range: drift back toward 0.5 slowly
        if pc.v.p_left > 0.5:
            pc.v.p_left = max(0.5, pc.v.p_left - 0.02)
        elif pc.v.p_left < 0.5:
            pc.v.p_left = min(0.5, pc.v.p_left + 0.02)

def check_update_rewarded_side():
    # Decide next trial's rewarded side.
    if pc.v.bias_correction:
        _update_side_probability()
        pc.v.rewarded_side = "left" if pc.withprob(pc.v.p_left) else "right"
    else:
        # Unbiased random (50/50)
        pc.v.rewarded_side = "left" if pc.withprob(0.5) else "right"
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

############
# All code below here is your existing task structure (unchanged flow),
# now calling the updated odor/helpers above. Bias tracking is updated in ITI.
############

# State machine
states = ["wait_for_center_poke", "deliver_odor", "wait_for_side_poke", "left_reward", "right_reward", "inter_trial_interval", "timeout"]
events = ["center_poke", "right_poke", "left_poke", "center_poke_out", "right_poke_out", "left_poke_out", "session_timer", "finish_ITI", "close_final_valve", "close_final_valve_done", "center_poke_held", "set_odor_valves_for_trial","therm_sync_ON"]
initial_state = "wait_for_center_poke"

# Odor parameters
pc.v.required_center_hold_duration = 300  # ms. Minimal prefill time before final valve.
pc.v.odor_delivery_duration = 500
pc.v.final_valve_flush_duration = 500  # ensure this is shorter than the ITI

# General Parameters.
pc.v.session_duration = 1 * pc.hour  # Session duration.
pc.v.reward_durations = [30,30]  # Reward delivery duration (ms) [left, right].
pc.v.rewarded_side = "left" if (pc.random() > 0.5) else "right"

pc.v.ITI_duration = 3 * pc.second  # Inter trial interval duration. Ensure this is longer than final valve flush duration.
pc.v.timeout_duration = 2 * pc.second  # timeout for wrong trials (in addition to ITI)

# Variables.
pc.v.entry_time = 0
pc.v.n_total_trials = 0
pc.v.n_early_errors = 0
pc.v.mov_ave_correct = 0  # moving avg of last 10 trials
pc.v.overall_ave_correct = 0  # excludes early errs

# Reward variables (updated / used in "is_rewarded")
pc.v.choice = "right"
pc.v.outcome = 0
pc.v.n_correct_trials = 0
pc.v.n_rewards = 0  # total number of rewards obtained.
pc.v.ave_correct_tracker = pc.OnlineMovingAverage(10)

### These funcs are auto-run at beginning + end ###
def run_start():
    # Set session timer and initialize odor for first trial
    pc.set_timer("session_timer", pc.v.session_duration)
    pc.publish_event("set_odor_valves_for_trial")

def run_end():
    # Turn off all hardware outputs.
    right_port.SOL.off()
    left_port.SOL.off()
    center_port.LED.off()
    disable_odor_valves()
    pc.print("SESSION_DONE")

# State-independent behaviour.
def all_states(event):
    # End session.
    if event == "session_timer":
        pc.stop_framework()

    # End flushing of final valve
    elif event == "close_final_valve":
        final_valve.off()

    # After new trial's odor is selected in ITI, set the odor valves
    # once the final valve is certainly closed.
    elif event == "set_odor_valves_for_trial":
        if pc.timer_remaining("close_final_valve_done") == 0:
            set_odor_valves()
        else:
            pc.set_timer("set_odor_valves_for_trial", 100)

### State-machine ###

def wait_for_center_poke(event):

    if event == "entry":
        center_port.LED.on()  # cues mouse that trial is available
        pc.v.entry_time = pc.get_current_time()  # start early-error buffer
        # set_odor_valves() handled via 'set_odor_valves_for_trial'

    # If mouse pokes either side port after early-error buffer, timeout and restart.
    elif (
        ((pc.get_current_time() - pc.v.entry_time) > 300)
        and (event == "left_poke" or event == "right_poke")
    ):
        center_port.LED.off()
        disable_odor_valves()
        pc.v.n_early_errors += 1
        pc.goto_state("timeout")

    # If still licking at reward port, restart the early-error buffer when it leaves.
    elif (event == "left_poke_out" or event == "right_poke_out"):
        pc.v.entry_time = pc.get_current_time()

    # Require mouse to hold nose in center.
    elif event == "center_poke":
        pc.set_timer("center_poke_held", pc.v.required_center_hold_duration)
    elif event == "center_poke_out":
        pc.disarm_timer("center_poke_held")
    elif event == "center_poke_held":
        pc.goto_state("deliver_odor")

def deliver_odor(event):
    if event == "entry":
        center_port.LED.off()  # cue timing of odor delivery
        final_valve.on()       # TTL -> final valve opens
        pc.timed_goto_state("wait_for_side_poke", pc.v.odor_delivery_duration)
    elif event == "exit":
        disable_odor_valves()  # allow final valve to flush clean air
        pc.set_timer("close_final_valve", pc.v.final_valve_flush_duration)
        pc.set_timer("close_final_valve_done", pc.v.final_valve_flush_duration + 200)

def wait_for_side_poke(event):
    if event == "right_poke":
        if is_rewarded("right"):
            pc.goto_state("right_reward")
        else:
            pc.goto_state("timeout")

    elif event == "left_poke":
        if is_rewarded("left"):
            pc.goto_state("left_reward")
        else:
            pc.goto_state("timeout")

def left_reward(event):
    if event == "entry":
        pc.timed_goto_state("inter_trial_interval", pc.v.reward_duration_multiplier * pc.v.reward_durations[0])
        left_port.SOL.on()
    elif event == "exit":
        left_port.SOL.off()

def right_reward(event):
    if event == "entry":
        pc.timed_goto_state("inter_trial_interval", pc.v.reward_duration_multiplier * pc.v.reward_durations[1])
        right_port.SOL.on()
    elif event == "exit":
        right_port.SOL.off()

def timeout(event):
    if event == "entry":
        pc.timed_goto_state("inter_trial_interval", pc.v.timeout_duration)

def inter_trial_interval(event):
    if event == "entry":
        # Start ITI timer (easy to extend without restarting state)
        pc.set_timer("finish_ITI", pc.v.ITI_duration)
        pc.v.entry_time = pc.get_current_time()

        # Update vars
        pc.v.n_total_trials += 1
        pc.v.mov_ave_correct = pc.v.ave_correct_tracker.ave
        pc.v.overall_ave_correct = pc.v.n_correct_trials / max(pc.v.n_total_trials - pc.v.n_early_errors, 1)
        pc.print_variables(["n_total_trials", "n_correct_trials", "n_early_errors", "mov_ave_correct", "overall_ave_correct", "rewarded_side", "choice", "outcome"])

        # Update bias estimator with the just-finished trial
        _record_choice_for_bias()

        # Prep next trial (decide side with/without bias correction; apply odor)
        do_other_ITI_logic()

    # If still licking the rewarded spout, extend ITI during first half
    elif (
        pc.v.outcome
        and (
            ((event == "left_poke") and pc.v.choice == "left")
            or ((event == "right_poke") and pc.v.choice == "right")
        )
        and ((pc.get_current_time() - pc.v.entry_time) < (pc.v.ITI_duration/2))
    ):
        pc.reset_timer("finish_ITI", pc.v.ITI_duration)

    elif event == "finish_ITI":
        pc.goto_state("wait_for_center_poke")

    elif event == "exit":
        if pc.v.n_rewards >= pc.v.n_allowed_rwds:
            pc.stop_framework()
