# A script for calibrating solenoids, derived from hardware_test.py in the examples.

from pyControl.utility import *
from hardware_definition import left_port, right_port, center_port

# Instantiate Devices.
# board = Breakout_1_2()
# left_poke = Poke(board.port_3, rising_event="left_poke", falling_event="left_poke_out")
# center_poke = Poke(board.port_4, rising_event="center_poke", falling_event="center_poke_out")
# right_poke = Poke(board.port_2, rising_event="right_poke", falling_event="right_poke_out")

# States and events.

states = [
    "init_state",
    "left_active",
    "right_active",
    "left_open",
    "right_open",
]

events = [
    "left_poke",
    "right_poke",
    "center_poke",
    "center_poke_out",
]

initial_state = "init_state"

# Variables
v.rwd_durations = [47, 54]  # Reward delivery duration (ms) [left, right].
v.n_rwds_for_calibration = 200
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
        center_port.LED.on()
        v.current_rwd = 0
    elif event == "exit":
        center_port.LED.off()
    elif event == "left_poke":
        goto_state("left_active")
    elif event == "right_poke":
        goto_state("right_active")


def left_active(event):
    # Poke center to trigger solenoid or right to go to state right_active.
    if event == "entry":
        left_port.LED.on()
    elif event == "exit":
        left_port.LED.off()
    elif event == "center_poke":
        goto_state("left_open")


def right_active(event):
    # Poke center to trigger solenoid or left to go to state left_active.
    if event == "entry":
        right_port.LED.on()
    elif event == "exit":
        right_port.LED.off()
    elif event == "center_poke":
        goto_state("right_open")


def left_open(event):
    # Trigger left solenoid while center poke IR beam remains broken.
    if event == "entry":
        left_port.SOL.on()
    elif event == "center_poke_out":
        left_port.SOL.off()
        goto_state("init_state")


def right_open(event):
    # Trigger left solenoid while center poke IR beam remains broken.
    if event == "entry":
        right_port.SOL.on()
    elif event == "center_poke_out":
        right_port.SOL.off()
        goto_state("init_state")
