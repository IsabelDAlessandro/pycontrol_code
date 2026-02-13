import pyControl.utility as pc
# from devices import Breakout_1_2, Poke, Digital_output
from time import sleep
from hardware_definition import *

# State machine
states = ["wait_for_center_poke", "flush"]

events = ["center_poke"]

initial_state = "wait_for_center_poke"



# Trials "start" here
def wait_for_center_poke(event):
    if event == "entry":
        odor_A.off()
        odor_B.off()

        # Turn on light
        center_port.LED.on()
        right_port.LED.off()
        left_port.LED.off()

    elif event == "center_poke":
        pc.goto_state("flush")
    

def flush(event):
    if event == "entry":
       odor_A.on()
       odor_B.on()
       center_port.LED.off()
       right_port.LED.on()
       left_port.LED.on()
    elif event == "center_poke":
        pc.goto_state("wait_for_center_poke")
