import pyControl.utility as pc
from devices import Breakout_1_2, Poke

# Define hardware
board = Breakout_1_2()
right_port = Poke(board.port_2, rising_event="right_poke", falling_event="right_poke_out")
left_port = Poke(board.port_3, rising_event="left_poke", falling_event="left_poke_out")

# State machine
states = ["wait_for_poke", "left_reward", "right_reward", "inter_trial_interval"]

events = ["poke", "right_poke", "left_poke", "right_poke_out", "left_poke_out", "session_timer"]

initial_state = "wait_for_poke"


# Parameters.
pc.v.session_duration = 0.5 * pc.hour  # Session duration.
pc.v.reward_durations = [47, 54]  # Reward delivery duration (ms) [left, right].
pc.v.ITI_duration = 2 * pc.second  # Inter trial interval duration.
pc.v.n_allowed_rwds_per_block_mean = 4
pc.v.n_allowed_rwds_per_block_max = 10
pc.v.n_allowed_rwds = 100

# Variables.
pc.v.rewarded_side = "left"  # initial; will be changed betw left and right
pc.v.n_rewards = 0  # Number of rewards obtained.
pc.v.n_rewards_in_block = 0

def get_new_rwds_in_block():
    v = min(
        int(round(pc.exp_rand(pc.v.n_allowed_rwds_per_block_mean), 0)),
        pc.v.n_allowed_rwds_per_block_max
    )
    v = max(v, 1)
    return v
pc.v.n_allowed_rwds_per_block = get_new_rwds_in_block()

# These funcs are auto-run at beginning + end
def run_start():
    # Set session timer and turn on houslight.
    pc.set_timer("session_timer", pc.v.session_duration)

def run_end():
    # Turn off all hardware outputs.
    right_port.SOL.off()
    left_port.SOL.off()

    # Do whatever else...save data maybe?
    pass

def is_rewarded(side):
    if side == pc.v.rewarded_side:
        pc.v.n_rewards_in_block += 1
        if pc.v.n_rewards_in_block >= pc.v.n_allowed_rwds_per_block:
            pc.v.rewarded_side = "left" if (pc.v.rewarded_side == "right") else "right"
            pc.v.n_rewards_in_block = 0
            pc.v.n_allowed_rwds_per_block = get_new_rwds_in_block()
        outcome = 1
    else:
        outcome = 0
    return outcome

### State behaviour functions ###

def wait_for_poke(event):
    if event == "right_poke":
        if is_rewarded("right"):
            pc.goto_state("right_reward")
            pc.v.n_rewards += 1
        else:
            pc.goto_state("inter_trial_interval")
    elif event == "left_poke":
        if is_rewarded("left"):
            pc.goto_state("left_reward")
            pc.v.n_rewards += 1
        else:
            pc.goto_state("inter_trial_interval")


def left_reward(event):
    # Deliver reward to left poke.
    if event == "entry":
        pc.timed_goto_state("inter_trial_interval", pc.v.reward_durations[0])
        left_port.SOL.on()
    elif event == "exit":
        left_port.SOL.off()


def right_reward(event):
    # Deliver reward to right poke.
    if event == "entry":
        pc.timed_goto_state("inter_trial_interval", pc.v.reward_durations[1])
        right_port.SOL.on()
    elif event == "exit":
        right_port.SOL.off()


def inter_trial_interval(event):
    # Go to init trial after specified delay.
    if event == "entry":
        pc.timed_goto_state("wait_for_poke", pc.v.ITI_duration)


# State independent behaviour.
def all_states(event):
    # When 'session_timer' event occurs stop framework to end session.
    if event == "session_timer":
        pc.stop_framework()
    if pc.v.n_rewards >= pc.v.n_allowed_rwds:
        pc.stop_framework()