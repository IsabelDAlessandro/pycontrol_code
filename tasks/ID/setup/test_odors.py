import pyControl.utility as pc
from hardware_definition import right_port, left_port, center_port, final_valve, odor_A, odor_B

states = ["wait_for_poke", "deliver_odor"]
events = ["center_poke", "right_poke", "left_poke", "center_poke_out", "right_poke_out", "left_poke_out", "session_timer", "finish_ITI", "close_final_valve", "center_poke_held"]

pc.v.final_valve_flush_duration = 10000
pc.v.odor_delivery_duration = 10000

"""
To test olfactometer final valve flushing:
With task running:
1) establish baseline by sticking PID into center a bunch of times.
    This will show you the blank response.
2) load an odor by poking a side port. Then stick the PID into the center.
    You should see an odor response.
3) Test the blank response again. Ideally, you won't see any transient.

"""

def set_odor_valves(side):
    if side == "left":
        odor_B.off()
        odor_A.on()
    elif side == "right":
        odor_A.off()
        odor_B.on()


def disable_odor_valves():
    odor_A.off()
    odor_B.off()


# State-independent behaviour.
def all_states(event):
    # When 'session_timer' event occurs stop framework to end session.
    if event == "session_timer":
        pc.stop_framework()
    elif event == "close_final_valve":
        final_valve.off()

# State machine
initial_state = "wait_for_poke"
def wait_for_poke(event):
    if event == "left_poke":
        set_odor_valves("left")
        center_port.LED.on()
    elif event == "right_poke":
        set_odor_valves("right")
        center_port.LED.on()
    elif event == "center_poke":
        pc.goto_state("deliver_odor")


def deliver_odor(event):
    if event == "entry":
        center_port.LED.off()
        final_valve.on()
        pc.timed_goto_state("wait_for_poke", pc.v.odor_delivery_duration)
    elif event == "exit":
        disable_odor_valves()
        pc.set_timer("close_final_valve", (pc.v.final_valve_flush_duration))

    