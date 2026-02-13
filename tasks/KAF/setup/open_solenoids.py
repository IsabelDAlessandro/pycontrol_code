# A script for calibrating solenoids, derived from hardware_test.py in the examples.

from pyControl.utility import *
from hardware_definition import right_port, left_port, center_port, final_valve


# Instantiate Devices.
# board = Breakout_1_2()
# left_port = Poke(board.port_3, rising_event="left_port", falling_event="left_port_out")
# center_port = Poke(board.port_4, rising_event="center_port", falling_event="center_port_out")
# right_port = Poke(board.port_2, rising_event="right_port", falling_event="right_port_out")

# States and events.

states = [
    "init_state",
    "open_solenoids"
]

events = [
    "left_poke",
    "right_poke",
    "center_poke",
    "center_poke_out",
]

initial_state = "init_state"

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
    elif event == "center_poke":
        goto_state("open_solenoids")
    elif event == "exit":
        center_port.LED.off()

def open_solenoids(event):
    if event == "entry":
        left_port.SOL.on()
        right_port.SOL.on()
    elif event == "center_poke":
        left_port.SOL.off()
        right_port.SOL.off()
        goto_state("init_state")