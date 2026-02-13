from pyControl.utility import *
from devices import Breakout_1_2, Digital_input, Digital_output
# from hardware_definition import left_port, right_port, center_port
import time

board = Breakout_1_2()
pushbutton = Digital_input(pin=board.button, falling_event='button', pull='up') 
a = Digital_output(pin=board.port_5.POW_A)
b = Digital_output(pin=board.port_5.POW_B)
# c = Digital_output(pin=board.port_6.POW_C)


states = [
    "wait",
    "test"
]

events = [
    "button"
]

initial_state = "wait"

def wait(event):
    if event == "button":
        goto_state("test")

def test(event):
    if event == "button":
        a.on()
        time.sleep(2)
        a.off()
        b.on()
        time.sleep(2)
        b.off()
        # b.on()
        # time.sleep(2)
        # b.off()
        goto_state("wait")