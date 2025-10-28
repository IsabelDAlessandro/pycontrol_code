import pyControl.utility as pc
from hardware_definition import right_port, left_port, center_port, final_valve, odor_A, odor_B, thermistor_sync, speaker

# =======================
# ===== CONFIG ==========
# =======================

# Tone frequency (plays whenever center LED is ON)
TONE_FREQ_1 = 4500  # Hz

# Non-target odors (B options) — EDIT THIS LIST to your Teensy manifold mapping.
# One of these channel numbers will be chosen at random each trial when B is required.
pc.v.non_target_odors = [2,3,4]
pc.v.B_current_valve = None  # chosen per trial when B is used

# Reward sizing
pc.v.reward_duration_multiplier = 0.75
pc.v.n_allowed_rwds = 150  # total per session
pc.v.choice_window_ms = 5000

# Shaping vars
pc.v.required_center_hold_duration = 200

# Rewards-per-block function (keep your shaping schedule here)
def get_n_rwds_allowed_in_block():
    pc.v.n_allowed_rwds_per_block = 10  # Day 1 example
    #c.v.n_allowed_rwds_per_block = 7
    # pc.v.n_allowed_rwds_per_block = 3
    # pc.v.n_allowed_rwds_per_block = 2 if pc.withprob(0.5) else 3
    # pc.v.n_allowed_rwds_per_block = 2 if pc.withprob(0.5) else (1 if pc.withprob(0.5) else 3)

# Block counters
pc.v.n_allowed_rwds_per_block = 10
pc.v.n_rewards_in_block = 0

# =======================
# ===== ODOR LOGIC ======
# =======================

def _choose_B_for_this_trial_if_needed():
    """Pick a non-target valve for B if we haven't already this trial."""
    if pc.v.B_current_valve is None:
        pc.v.B_current_valve = pc.choice(pc.v.non_target_odors)
        odor_B.set_valve(pc.v.B_current_valve)

# For this shaping task:
#   - If left is rewarded this trial -> present A (fixed)  -> left is correct.
#   - If right is rewarded this trial -> present B (random) -> right is correct.
def set_odor_valves():
    if pc.v.rewarded_side == "left":
        odor_B.off()
        odor_A.on()
    elif pc.v.rewarded_side == "right":
        _choose_B_for_this_trial_if_needed()
        odor_A.off()
        odor_B.on()

def disable_odor_valves():
    odor_A.off()
    odor_B.off()

# ============ Reward-side / block helpers ============

def do_other_ITI_logic():
    # Prepare next trial's reward side by block logic
    check_update_rewarded_side()
    # Reset B choice so the next right-rewarded trial picks a fresh non-target
    pc.v.B_current_valve = None
    # Ask the all_states handler to (re)apply selected odor once it's safe
    pc.publish_event("set_odor_valves_for_trial")

def check_update_rewarded_side():
    # Keep your per-block shaping, but DO NOT alter A/B mapping:
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

############
# All code below here is your original task structure, with tone + TTL final valve integrated.
############

# State machine
states = ["wait_for_center_poke", "deliver_odor", "wait_for_side_poke", "left_reward", "right_reward", "inter_trial_interval", "timeout"]
events = ["center_poke", "right_poke", "left_poke", "center_poke_out", "right_poke_out", "left_poke_out", "session_timer", "finish_ITI", "close_final_valve", "close_final_valve_done", "center_poke_held", "set_odor_valves_for_trial","therm_sync_ON","choice_window_over","svf_recheck" ]
initial_state = "wait_for_center_poke"

# Odor parameters
pc.v.odor_delivery_duration = 500
pc.v.final_valve_flush_duration = 1000  # ensure this is shorter than the ITI

# General Parameters
pc.v.session_duration = 1 * pc.hour
pc.v.reward_durations = [47, 54]  # [left, right] ms
pc.v.rewarded_side = "left" if (pc.random() > 0.5) else "right"  # block starts left or right

pc.v.ITI_duration = 3 * pc.second  # must exceed final valve flush duration
pc.v.timeout_duration = 2 * pc.second
pc.v.timeout_early_ms = 500# penalty for EARLY side pokes (during wait_for_center_poke)
pc.v.timeout_wrong_ms = 2000   # penalty for WRONG choice after a valid center hold
pc.v.early_error_buffer_duration = 300 #ms

# Variables
pc.v.entry_time = 0
pc.v.n_total_trials = 0
pc.v.n_early_errors = 0
pc.v.mov_ave_correct = 0
pc.v.overall_ave_correct = 0

# Reward tracking
pc.v.choice = "right"
pc.v.outcome = 0
pc.v.n_correct_trials = 0
pc.v.n_rewards = 0
pc.v.ave_correct_tracker = pc.OnlineMovingAverage(10)

### Run hooks ###
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
            # don't stack timers; just reset the existing one
            pc.reset_timer("svf_recheck", 50)
### State-machine ###

def wait_for_center_poke(event):

    if event == "entry":
        # Cue trial availability
        center_port.LED.on()
        speaker.sine(TONE_FREQ_1)  # tone ON with LED
        pc.v.entry_time = pc.get_current_time()  # start early-error buffer

    elif (
        ((pc.get_current_time() - pc.v.entry_time) > pc.v.early_error_buffer_duration)
        and (event == "left_poke" or event == "right_poke")
    ):
        center_port.LED.off()
        speaker.off()  # tone OFF with LED
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
        # LED OFF cues timing; tone OFF with LED
        center_port.LED.off()
        speaker.off()
        # TTL opens final valve; Teensy already on selected A or B (random) from ITI
        final_valve.on()
        pc.timed_goto_state("wait_for_side_poke", pc.v.odor_delivery_duration)

    elif event == "exit":
        # Allow final valve to flush clean air; ensure manifold closed/blank
        disable_odor_valves()
        pc.set_timer("close_final_valve", pc.v.final_valve_flush_duration)
        pc.set_timer("close_final_valve_done", pc.v.final_valve_flush_duration + 200)

def wait_for_side_poke(event):
    if event == "entry":
        # Optional deadline for making the correct choice
        if pc.v.choice_window_ms > 0:
            pc.set_timer("choice_window_over", pc.v.choice_window_ms)

    elif event == "left_poke":
        # Only reward if LEFT is the correct side; otherwise ignore and keep waiting
        if pc.v.rewarded_side == "left":
            if is_rewarded("left"):
                pc.goto_state("left_reward")

    elif event == "right_poke":
        # Only reward if RIGHT is the correct side; otherwise ignore and keep waiting
        if pc.v.rewarded_side == "right":
            if is_rewarded("right"):
                pc.goto_state("right_reward")

    elif event == "choice_window_over":
        # No correct choice was made in time -> end trial without reward
        pc.v.outcome = 0
        pc.v.ave_correct_tracker.add(0)
        pc.goto_state("inter_trial_interval")


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
        pc.set_timer("finish_ITI", pc.v.ITI_duration)
        pc.v.entry_time = pc.get_current_time()

        # Update stats
        pc.v.n_total_trials += 1
        pc.v.mov_ave_correct = pc.v.ave_correct_tracker.ave
        pc.v.overall_ave_correct = pc.v.n_correct_trials / max(pc.v.n_total_trials - pc.v.n_early_errors, 1)
        pc.print_variables(["n_total_trials", "n_correct_trials", "n_early_errors", "mov_ave_correct", "overall_ave_correct", "rewarded_side", "choice", "outcome"])

        # Auto-increase center hold duration for shaping
        if (
            ((pc.v.n_rewards == 25) or (pc.v.n_rewards == 50))
            and (pc.v.required_center_hold_duration < 300)
        ):
            pc.v.required_center_hold_duration += 75

        # Per-trial logic (block rule + select next odor)
        do_other_ITI_logic()

    elif (
        pc.v.outcome
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
