# A script for calibrating solenoids, derived from hardware_test.py in the examples.

from pyControl.utility import *
from devices import *

# Instantiate Devices.
board = Breakout_1_2()
valve_A = Digital_output(pin=board.port_1.POW_A)
valve_B = Digital_output(pin=board.port_1.POW_B)
valve_C = Digital_output(pin=board.port_1.POW_C)

states = [
    "off",
    "A_on",
    "B_on",
    "C_on",
]
events = []
initial_state = "off"
v.off_duration = 500
v.on_duration = 5000


def run_start():
    pass

def run_end():
    pass


# State behaviour functions.
def off(event):
    if event == "entry":
        timed_goto_state("A_on", v.off_duration)
        # timed_goto_state("A_on", 100)

def A_on(event):
    if event == "entry":
        # valve_A.on()
        # timed_goto_state("B_on", v.on_duration)
        timed_goto_state("B_on", 100)
    elif event == "exit":
        valve_A.off()

def B_on(event):
    if event == "entry":
        # valve_B.on()
        # timed_goto_state("C_on", v.on_duration)
        timed_goto_state("C_on", 100)
    elif event == "exit":
        valve_B.off()

def C_on(event):
    if event == "entry":
        valve_C.on()
        timed_goto_state("off", v.on_duration)
    elif event == "exit":
        valve_C.off()