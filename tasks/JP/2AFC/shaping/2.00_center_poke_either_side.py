import pyControl.utility as pc
from devices import Breakout_1_2, Poke, Digital_output

# Goal: teach mouse to poke in the center port first. Anything else while
# the light is on is bad. Then can go to either side for a reward.


# Define hardware
board = Breakout_1_2()
right_port = Poke(board.port_2, rising_event="right_poke", falling_event="right_poke_out")
left_port = Poke(board.port_3, rising_event="left_poke", falling_event="left_poke_out")
center_port = Poke(board.port_4, rising_event="center_poke", falling_event="center_poke_out")
final_valve = Digital_output(pin=board.port_1.POW_C)

# State machine
states = ["wait_for_center_poke", "hold_center_poke", "deliver_odor", "wait_for_side_poke", "left_reward", "right_reward", "inter_trial_interval", "timeout"]

events = ["center_poke", "right_poke", "left_poke", "center_poke_out", "right_poke_out", "left_poke_out", "session_timer"]

initial_state = "wait_for_center_poke"

# Odor parameters
pc.v.required_center_hold_duration = 75  # ms
pc.v.odor_delivery_duration = 500

# General Parameters.
pc.v.session_duration = 1 * pc.hour  # Session duration.
pc.v.reward_durations = [47, 54]  # Reward delivery duration (ms) [left, right].
pc.v.reward_duration_multiplier = 1.25
pc.v.ITI_duration = 1.5 * pc.second  # Inter trial interval duration.
pc.v.timeout_duration = 2 * pc.second  # timeout for wrong trials (in addition to ITI)
pc.v.n_allowed_rwds = 100  # total per session


# Variables.
pc.v.n_rewards = 0  # total number of rewards obtained.
pc.v.outcome = 0
pc.v.choice = "right"
pc.v.entry_time = 0
pc.v.n_total_trials = 0
pc.v.n_correct_trials = 0
pc.v.ave_correct_tracker = pc.OnlineMovingAverage(10)
pc.v.mov_ave_correct = 0  # moving avg of last ^^ trials
pc.v.vars_printed = False

# TODO: during reward licking, in addition to restarting ITI if still licking,
# if the first thing that happens is a poke OUT and then a poke, they shouldnt be penalized.
# So poke OUT during wait for center poke should generate an ineligibility period for errors. 

# These funcs are auto-run at beginning + end
def run_start():
    # Set session timer and turn on houslight.
    pc.set_timer("session_timer", pc.v.session_duration)

def run_end():
    # Turn off all hardware outputs.
    right_port.SOL.off()
    left_port.SOL.off()
    center_port.LED.off()

    # Do whatever else...save data maybe?
    pass


def is_rewarded(side):
    ### Always rewarded in this task
    pc.v.choice = side
    pc.v.outcome = 1
    pc.v.n_correct_trials += 1
    pc.v.ave_correct_tracker.add(1)
    return pc.v.outcome

### State behaviour functions ###

def wait_for_center_poke(event):

    if event == "entry":
        center_port.LED.on()
        pc.v.entry_time = pc.get_current_time()  # Start early-error buffer
    
    # If mouse pokes either side port *after* the early-error buffer
    # has elapsed, then timeout and restart the trial.
    elif (
        ((pc.get_current_time() - pc.v.entry_time) > 300)
        and (event == "left_poke" or event == "right_poke")
    ):
        center_port.LED.off()
        pc.goto_state("timeout")

    # If ms is still licking at reward port, then restart the 
    # early-error buffer when it leaves the side port.
    elif (event == "left_poke_out" or event == "right_poke_out"):
        pc.v.entry_time = pc.get_current_time()

    elif event == "center_poke":
        pc.goto_state("hold_center_poke")


# Require mouse to hold nose in center port for a certain amt of time
# If not, it's not an error, just nothing happens.
def hold_center_poke(event):
    if event == "entry":
        pc.timed_goto_state("deliver_odor", pc.v.required_center_hold_duration)
    elif event == "center_poke_out":
        pc.goto_state("wait_for_center_poke")  # cancels the timed transition


# Just air in this shaping task
def deliver_odor(event):
    if event == "entry":
        center_port.LED.off()
        final_valve.on()
        pc.timed_goto_state("wait_for_side_poke", pc.v.odor_delivery_duration)
    elif event == "exit":
        final_valve.off()


def wait_for_side_poke(event):
    if event == "entry":
        center_port.LED.off()

    elif event == "right_poke":
        if is_rewarded("right"):
            pc.goto_state("right_reward")
            pc.v.n_rewards += 1

    elif event == "left_poke":
        if is_rewarded("left"):
            pc.goto_state("left_reward")
            pc.v.n_rewards += 1


def left_reward(event):
    # Deliver reward to left poke.
    if event == "entry":
        pc.timed_goto_state("inter_trial_interval", pc.v.reward_duration_multiplier * pc.v.reward_durations[0])
        left_port.SOL.on()
    elif event == "exit":
        left_port.SOL.off()


def right_reward(event):
    # Deliver reward to right poke.
    if event == "entry":
        pc.timed_goto_state("inter_trial_interval", pc.v.reward_duration_multiplier * pc.v.reward_durations[1])
        right_port.SOL.on()
    elif event == "exit":
        right_port.SOL.off()

def timeout(event):
    if event == "entry":
        pc.v.ave_correct_tracker.add(0)
        pc.timed_goto_state("inter_trial_interval", pc.v.timeout_duration)


def inter_trial_interval(event):
    # Go to init trial after specified delay.
    if event == "entry":
        pc.timed_goto_state("wait_for_center_poke", pc.v.ITI_duration)
        pc.v.n_total_trials += 1
        pc.v.entry_time = pc.get_current_time()
        pc.v.mov_ave_correct = pc.v.ave_correct_tracker.ave
        if not pc.v.vars_printed:
            # prevent vars from being printed every time mouse licks in ITI...
            pc.print_variables(["n_total_trials", "n_correct_trials", "mov_ave_correct", "required_center_hold_duration"])
            pc.v.vars_printed = True
    elif (
        ((event == "left_poke") or (event == "right_poke"))
        and ((pc.get_current_time() - pc.v.entry_time) < (pc.v.ITI_duration/2))
    ):
        # If mouse is still licking the reward, let it keep going until it's done.
        # TODO: only do this on correct trials and for the correct port!
        pc.goto_state("inter_trial_interval")
    elif event == "exit":
        pc.v.vars_printed = False


# State independent behaviour.
def all_states(event):
    # When 'session_timer' event occurs stop framework to end session.
    if event == "session_timer":
        pc.stop_framework()
    if pc.v.n_rewards >= pc.v.n_allowed_rwds:
        pc.stop_framework()