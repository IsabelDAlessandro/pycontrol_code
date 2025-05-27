# A script for calibrating solenoids, derived from hardware_test.py in the examples.

from pyControl.utility import *
from devices import *

# Instantiate Devices.
board = Breakout_1_2()
left_poke = Poke(board.port_3, rising_event="left_poke", falling_event="left_poke_out")
center_poke = Poke(board.port_4, rising_event="center_poke", falling_event="center_poke_out")
right_poke = Poke(board.port_2, rising_event="right_poke", falling_event="right_poke_out")

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
        center_poke.LED.on()
        v.current_rwd = 0
    elif event == "center_poke":
        goto_state("open_solenoids")
    elif event == "exit":
        center_poke.LED.off()

def open_solenoids(event):
    if event == "entry":
        left_poke.SOL.on()
        right_poke.SOL.on()
    elif event == "center_poke":
        left_poke.SOL.off()
        right_poke.SOL.off()
        goto_state("init_state")