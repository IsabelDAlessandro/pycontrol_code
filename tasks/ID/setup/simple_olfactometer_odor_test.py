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


pc.v.required_center_hold_duration = 500  # ms
pc.v.odor_delivery_duration = 500
pc.v.rewarded_side = "left"
pc.v.reward_duration_multiplier = 1.25
pc.v.choice = "left"
pc.v.outcome = 0
pc.v.ITI_duration = 1000
pc.v.timeout_duration = 1000
pc.v.reward_durations = [47, 54]  # Reward delivery duration (ms) [left, right].
pc.v.n_rewards = 0

# Just switch every trial for this simple testing task
def is_rewarded(side):
    pc.v.choice = side
    if side == pc.v.rewarded_side:
        pc.v.rewarded_side = "left" if (pc.v.rewarded_side == "right") else "right"
        pc.v.outcome = 1
    else:
        pc.v.outcome = 0
    return pc.v.outcome


def inter_trial_interval(event):
    if event == "entry":
        
        # Report some vars
        pc.print_variables(["rewarded_side", "choice", "outcome"])
        
        # Clean out odor port
        final_valve.on()

        # Enforce ITI
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
        
        # Turn on light
        center_port.LED.on()

    elif event == "center_poke":
        pc.goto_state("hold_center_poke")
    

def hold_center_poke(event):
    if event == "entry":
        pc.timed_goto_state("deliver_odor", pc.v.required_center_hold_duration)
    elif event == "center_poke_out":
        pc.goto_state("wait_for_center_poke")  # cancels the timed transition


def deliver_odor(event):
    if event == "entry":
        final_valve.on()
        pc.timed_goto_state("wait_for_side_poke", pc.v.odor_delivery_duration)
    elif event == "exit":
        final_valve.off()
        odor_A.off()
        odor_B.off()
        center_port.LED.off()


def wait_for_side_poke(event):
    if event == "right_poke":
        if is_rewarded("right"):
            pc.v.n_rewards += 1
            pc.goto_state("right_reward")
        else:
            pc.goto_state("timeout")
    elif event == "left_poke":
        if is_rewarded("left"):
            pc.v.n_rewards += 1
            pc.goto_state("left_reward")
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



def run_end():
    # Turn off all hardware outputs.
    right_port.SOL.off()
    left_port.SOL.off()
    center_port.LED.off()
    odor_A.off()
    odor_B.off()
    final_valve.off()

    # Do whatever else...save data maybe?
    pass
