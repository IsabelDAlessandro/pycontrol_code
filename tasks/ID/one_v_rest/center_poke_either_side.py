import pyControl.utility as pc
from hardware_definition import right_port, left_port, center_port, final_valve, speaker  # Make sure speaker is imported

# =======================
# ===== PARAMETERS ======
# =======================



# Odor / final valve timing (ms)
pc.v.required_center_hold_duration = 150 #target: 300
pc.v.odor_delivery_duration = 500
pc.v.final_valve_flush_duration = 1000

# Session / reward / ITI
pc.v.session_duration = 1 * pc.hour
pc.v.reward_durations = [47, 54]  # [left, right] ms
pc.v.reward_duration_multiplier = 0.75
pc.v.ITI_duration = 3 * pc.second
pc.v.timeout_duration = 2 * pc.second
pc.v.timeout_early_ms = 500# penalty for EARLY side pokes (during wait_for_center_poke)
pc.v.early_error_buffer_duration = 500#ms
pc.v.n_allowed_rwds = 200

# Stats / trackers
pc.v.entry_time = 0
pc.v.n_total_trials = 0
pc.v.mov_ave_correct = 0
pc.v.choice = "right"
pc.v.outcome = 0
pc.v.n_correct_trials = 0
pc.v.n_rewards = 0
pc.v.ave_correct_tracker = pc.OnlineMovingAverage(10)

# ---- Teensy olfactometer serial (optional) ----
# If you want this task to explicitly select the blank line on the Teensy,
# set the blank manifold valve number here (e.g., 8). If None, no serial is sent.
BLANK_ODOR_VALVE_NUM = None #- set to an int (e.g., 8) if you want explicit blank selection.

BRIDGE_TAG = "#OLF:"  # tag your TSV bridge watches for


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
    "center_poke",
    "right_poke",
    "left_poke",
    "center_poke_out",
    "right_poke_out",
    "left_poke_out",
    "session_timer",
    "finish_ITI",
    "close_final_valve",
    "center_poke_held",
]

initial_state = "wait_for_center_poke"


# =======================
# ===== RUN HOOKS  ======
# =======================

def run_start():
    # Set session timer.
    pc.set_timer("session_timer", pc.v.session_duration)


def run_end():
    # Turn off all hardware outputs.
    right_port.SOL.off()
    left_port.SOL.off()
    center_port.LED.off()
    disable_odor_valves()
    pc.print("SESSION_DONE")


# =======================
# ===== HELPERS    ======
# =======================

def is_rewarded(side):
    """Always rewarded in this shaping task."""
    pc.v.choice = side
    pc.v.outcome = 1
    pc.v.n_correct_trials += 1
    pc.v.n_rewards += 1
    pc.v.ave_correct_tracker.add(1)
    return 1


def set_odor_valves():
    """
    For this shaping task we deliver BLANK air.
    If BLANK_ODOR_VALVE_NUM is set, tell the Teensy to select that valve.
    Otherwise do nothing (assumes Teensy already sits on blank).
    """
    if BLANK_ODOR_VALVE_NUM is not None:
        pc.print("{}o{}".format(BRIDGE_TAG, BLANK_ODOR_VALVE_NUM))


def disable_odor_valves():
    if BLANK_ODOR_VALVE_NUM is not None:
        pc.print("{}c{}".format(BRIDGE_TAG, BLANK_ODOR_VALVE_NUM))  # open blank




def do_other_ITI_logic():
    pass


# State-independent behaviour.
def all_states(event):
    # End session.
    if event == "session_timer":
        pc.stop_framework()
    # Close final valve after flush window.
    elif event == "close_final_valve":
        final_valve.off()


# =======================
# ===== STATES      =====
# =======================

def wait_for_center_poke(event):

    # Cue mouse that trial is available
    if event == "entry":
        center_port.LED.on()
        pc.v.entry_time = pc.get_current_time()
        set_odor_valves()

    # Side poke after early-error buffer -> timeout.
    elif (
        ((pc.get_current_time() - pc.v.entry_time) > pc.v.early_error_buffer_duration)
        and (event == "left_poke" or event == "right_poke")
    ):
        center_port.LED.off()
        disable_odor_valves()
        pc.v.timeout_duration = pc.v.timeout_early_ms
        pc.goto_state("timeout")

    # If still licking at reward port, restart early-error buffer when they leave.
    elif (event == "left_poke_out" or event == "right_poke_out"):
        pc.v.entry_time = pc.get_current_time()

    # Require a brief hold in center before delivery.
    elif event == "center_poke":
        pc.set_timer("center_poke_held", pc.v.required_center_hold_duration)
    elif event == "center_poke_out":
        pc.disarm_timer("center_poke_held")
    elif event == "center_poke_held":
        pc.goto_state("deliver_odor")


# Just air in this shaping task
def deliver_odor(event):
    if event == "entry":
        center_port.LED.off()
        # Open final valve (TTL to Teensy gate); Teensy should already be on blank
        final_valve.on()
        pc.timed_goto_state("wait_for_side_poke", pc.v.odor_delivery_duration)

    elif event == "exit":
        # Close final valve after flush window; also ensure manifold reset
        pc.set_timer("close_final_valve", pc.v.final_valve_flush_duration)
        disable_odor_valves()


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
    # Deliver reward to left poke.
    if event == "entry":
        pc.timed_goto_state(
            "inter_trial_interval",
            pc.v.reward_duration_multiplier * pc.v.reward_durations[0],
        )
        left_port.SOL.on()
    elif event == "exit":
        left_port.SOL.off()


def right_reward(event):
    # Deliver reward to right poke.
    if event == "entry":
        pc.timed_goto_state(
            "inter_trial_interval",
            pc.v.reward_duration_multiplier * pc.v.reward_durations[1],
        )
        right_port.SOL.on()
    elif event == "exit":
        right_port.SOL.off()


def timeout(event):
    if event == "entry":
        pc.v.ave_correct_tracker.add(0)
        pc.timed_goto_state("inter_trial_interval", pc.v.timeout_duration)


def inter_trial_interval(event):
    if event == "entry":
        # Start ITI timer.
        pc.set_timer("finish_ITI", pc.v.ITI_duration)
        pc.v.entry_time = pc.get_current_time()

        # Update vars / print summary
        pc.v.mov_ave_correct = pc.v.ave_correct_tracker.ave
        pc.v.n_total_trials += 1
        pc.print_variables(
            ["n_total_trials", "n_correct_trials", "mov_ave_correct", "required_center_hold_duration"]
        )

        # Auto-increase center hold duration for shaping
        if (
            ((pc.v.n_rewards == 25) or (pc.v.n_rewards == 50))
            and (pc.v.required_center_hold_duration < 300)
        ):
            pc.v.required_center_hold_duration += 75

        do_other_ITI_logic()

    # If mouse is still licking the reward, extend ITI in the first half.
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
