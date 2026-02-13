# ID/setup/olf_valve_cycler_gate_off.py
import pyControl.utility as pc
from hardware_definition import final_valve

# --- Config ---
pc.v.valves          = [1, 2, 3]   # valves to cycle
pc.v.repeats         = 3           # how many times to run through the list
pc.v.on_to_off_ms    = 2000        # delay from ON -> OFF (2 s)
pc.v.off_to_next_on_ms = 10000     # delay from OFF -> next valve ON (10 s)

# Internal trackers
pc.v.idx   = 0        # index in pc.v.valves
pc.v.rep   = 0        # completed list cycles
pc.v.phase = 'on'     # 'on' or 'off'

states = ['cycle', 'done']
events = ['tick']
initial_state = 'cycle'

def run_start():
    # Make sure gate TTL is LOW so Teensy applies valve commands immediately.
    final_valve.off()

def _send_open(n):
    pc.print('#OLF:o{}'.format(int(n)))

def _send_close(n):
    pc.print('#OLF:c{}'.format(int(n)))

def cycle(event):
    if event == 'entry':
        # Kick the stepper with a tiny delay so we never transition out of 'entry'.
        pc.set_timer('tick', 1)

    elif event == 'tick':
        # Finished all repeats?
        if pc.v.rep >= pc.v.repeats:
            pc.goto_state('done')
            return

        valve = pc.v.valves[pc.v.idx]

        if pc.v.phase == 'on':
            _send_open(valve)
            pc.v.phase = 'off'
            pc.set_timer('tick', pc.v.on_to_off_ms)

        else:  # phase == 'off'
            _send_close(valve)
            pc.v.phase = 'on'
            # advance to next valve
            pc.v.idx += 1
            if pc.v.idx >= len(pc.v.valves):
                pc.v.idx = 0
                pc.v.rep += 1
            pc.set_timer('tick', pc.v.off_to_next_on_ms)

def done(event):
    if event == 'entry':
        final_valve.off()
        pc.print('CYCLE_DONE')
        pc.stop_framework()
