# A script for calibrating solenoids, derived from hardware_test.py in the examples.

from pyControl.utility import *
from devices import *

# Instantiate Devices.
board = Breakout_1_2()
left_poke = Poke(board.port_1, rising_event="left_poke", falling_event="left_poke_out")
center_poke = Poke(board.port_2, rising_event="center_poke", falling_event="center_poke_out")
right_poke = Poke(board.port_3, rising_event="right_poke", falling_event="right_poke_out")

# States and events.

states = [
    "init_state",
    "left_active",
    "right_active",
    "left_calibration",
    "left_wait",
    "right_calibration",
    "right_wait",
]

events = [
    "left_poke",
    "right_poke",
    "center_poke",
    "center_poke_out",
]

initial_state = "init_state"

# Variables
v.rwd_durations = [50, 50]  # Reward delivery duration (ms) [left, right].
v.n_rwds_for_calibration = 100
v.current_rwd = 0  # Current reward number


# Run start and stop behaviour.


def run_start():
    pass

def run_end():
    pass


# State behaviour functions.
def init_state(event):
    # Select left or right poke.
    if event == "entry":
        center_poke.LED.on()
        v.current_rwd = 0
    elif event == "exit":
        center_poke.LED.off()
    elif event == "left_poke":
        goto_state("left_active")
    elif event == "right_poke":
        goto_state("right_active")


def left_active(event):
    # Poke center to trigger solenoid or right to go to state right_active.
    if event == "entry":
        left_poke.LED.on()
    elif event == "exit":
        left_poke.LED.off()
    elif event == "center_poke":
        goto_state("left_calibration")


def right_active(event):
    # Poke center to trigger solenoid or left to go to state left_active.
    if event == "entry":
        right_poke.LED.on()
    elif event == "exit":
        right_poke.LED.off()
    elif event == "center_poke":
        goto_state("right_calibration")


def left_calibration(event):
    # Trigger left solenoid while center poke IR beam remains broken.
    if event == "entry":
        if v.current_rwd >= v.n_rwds_for_calibration:
            # Stop calibration after n rewards.
            goto_state("init_state")
        else:
            left_poke.SOL.on()
            v.current_rwd += 1
            timed_goto_state("left_wait", v.rwd_durations[0])
    elif event == "exit":
        left_poke.SOL.off()

def left_wait(event):
    if event == "entry":
        timed_goto_state("left_calibration", 100)  # pause between each rwd delivery to allow the solenoid to fully close


def right_calibration(event):
    # Trigger right solenoid while center poke IR beam remains broken.
    if event == "entry":
        v.current_rwd += 1
        right_poke.SOL.on()
        timed_goto_state("right_wait", v.rwd_durations[1])
    elif event == "exit":
        right_poke.SOL.off()

def right_wait(event):
    if event == "entry":
        timed_goto_state("right_calibration", 100)  # pause between each rwd delivery to allow the solenoid to fully close