import pyControl.utility as pc
from devices import Breakout_1_2, Poke, Digital_output
from time import sleep

# Define hardware
board = Breakout_1_2()
right_port = Poke(board.port_2, rising_event="right_poke", falling_event="right_poke_out")
left_port = Poke(board.port_3, rising_event="left_poke", falling_event="left_poke_out")
center_port = Poke(board.port_4, rising_event="center_poke", falling_event="center_poke_out")
odor_A = Digital_output(pin=board.port_1.POW_A)
odor_B = Digital_output(pin=board.port_1.POW_B)
final_valve = Digital_output(pin=board.port_1.POW_C)

# State machine
states = ["wait_for_center_poke", "hold_center_poke", "deliver_odor", "wait_for_side_poke", "left_reward", "right_reward", "inter_trial_interval", "timeout"]

events = ["center_poke", "right_poke", "left_poke", "center_poke_out", "right_poke_out", "left_poke_out", "session_timer"]

initial_state = "inter_trial_interval"


# Odor parameters
pc.v.required_center_hold_duration = 500  # ms
pc.v.odor_delivery_duration = 500

# General Parameters.
pc.v.session_duration = 1 * pc.hour  # Session duration.
pc.v.ITI_duration = 1.5 * pc.second  # Inter trial interval duration.

# Reward / timeout params
pc.v.timeout_duration = 6 * pc.second  # timeout for wrong trials (in addition to ITI)
pc.v.reward_durations = [47, 54]  # Reward delivery duration (ms) [left, right].
pc.v.reward_duration_multiplier = 1.25
pc.v.n_allowed_rwds_per_block_mean = 8
pc.v.n_allowed_rwds_per_block_min = 6
pc.v.n_allowed_rwds_per_block_max = 10
pc.v.n_allowed_rwds = 100  # total per session

# Variables.
pc.v.rewarded_side = "left"  # initial; will be changed betw left and right
pc.v.n_rewards = 0  # total number of rewards obtained.
pc.v.n_rewards_in_block = 0  # per-block counter
pc.v.outcome = 0
pc.v.choice = "right"
pc.v.correct_mov_ave = pc.Exp_mov_ave(tau=10, init_value=0.5)  # Moving average of correct/incorrect choices
pc.v.ave_correct = 0.5


def get_new_rwds_in_block():
    v = min(
        int(round(pc.gauss_rand(pc.v.n_allowed_rwds_per_block_mean, 1), 0)),
        pc.v.n_allowed_rwds_per_block_max
    )
    v = max(v, pc.v.n_allowed_rwds_per_block_min)
    return v
pc.v.n_allowed_rwds_per_block = get_new_rwds_in_block()


def check_update_rewarded_side():
    if pc.v.n_rewards_in_block >= pc.v.n_allowed_rwds_per_block:
        pc.v.rewarded_side = "left" if (pc.v.rewarded_side == "right") else "right"
        pc.v.n_rewards_in_block = 0
        pc.v.n_allowed_rwds_per_block = get_new_rwds_in_block()
    return

def is_rewarded(side):
    pc.v.choice = side
    if side == pc.v.rewarded_side:
        pc.v.n_rewards_in_block += 1
        pc.v.outcome = 1
    else:
        pc.v.outcome = 0
    pc.v.correct_mov_ave.update(pc.v.outcome)
    pc.v.ave_correct = pc.v.correct_mov_ave.value
    return pc.v.outcome

### State behaviour functions ###

# These funcs are auto-run at beginning + end
def run_start():
    # Set session timer and turn on houslight.
    pc.set_timer("session_timer", pc.v.session_duration)

def run_end():
    # Turn off all hardware outputs.
    right_port.SOL.off()
    left_port.SOL.off()
    center_port.LED.off()
    final_valve.off()
    odor_A.off()
    odor_B.off()

    # Do whatever else...save data maybe?
    pass


def inter_trial_interval(event):
    # Go to init trial after specified delay.
    if event == "entry":
        pc.print_variables(["rewarded_side", "choice", "outcome",  "n_rewards_in_block",  "ave_correct"])
        
         # Clean out odor port
        final_valve.on()

        check_update_rewarded_side()  # importantly do this after previous trial info has been printed
        pc.timed_goto_state("wait_for_center_poke", pc.v.ITI_duration)
    
    elif event == "exit":
        final_valve.off()

# Trials "start" here
def wait_for_center_poke(event):
    if event == "entry":

        # Set odors
        sleep(0.1)  # allow time for final valve to fully close
        if pc.v.rewarded_side == "left":
            odor_B.off()
            odor_A.on()
        elif pc.v.rewarded_side == "right":
            odor_A.off()
            odor_B.on()

        center_port.LED.on()
    elif event == "left_poke" or event == "right_poke":
        odor_A.off()
        odor_B.off()
        center_port.LED.off()
        pc.goto_state("timeout")

    elif event == "center_poke":
        pc.goto_state("hold_center_poke")
    

def hold_center_poke(event):
    if event == "entry":
        pc.timed_goto_state("deliver_odor", pc.v.required_center_hold_duration)
    elif event == "center_poke_out":
        pc.goto_state("wait_for_center_poke")  # cancels the timed transition


def deliver_odor(event):
    if event == "entry":
        center_port.LED.off()
        final_valve.on()
        pc.timed_goto_state("wait_for_side_poke", pc.v.odor_delivery_duration)
    elif event == "exit":
        final_valve.off()
        odor_A.off()
        odor_B.off()


def wait_for_side_poke(event):
    if event == "right_poke":
        if is_rewarded("right"):
            pc.goto_state("right_reward")
            pc.v.n_rewards += 1
        else:
            pc.goto_state("timeout")
    elif event == "left_poke":
        if is_rewarded("left"):
            pc.goto_state("left_reward")
            pc.v.n_rewards += 1
        else:
            pc.goto_state("timeout")


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
        pc.timed_goto_state("inter_trial_interval", pc.v.timeout_duration)


# State independent behaviour.
def all_states(event):
    # When 'session_timer' event occurs stop framework to end session.
    if event == "session_timer":
        pc.stop_framework()
    if pc.v.n_rewards >= pc.v.n_allowed_rwds:
        pc.stop_framework()