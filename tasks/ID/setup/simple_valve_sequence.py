# olf_valve_cycle_test.py
# Cycles a set of manifold valves by printing "#OLF:oN" / "#OLF:cN" lines.
# Your olf_bridge_tail.py will forward these to the Teensy.

import pyControl.utility as pc

# ======= User config =======
pc.v.valves        = [1, 2, 3]   # which valve numbers to test
pc.v.repeats       = 3           # number of full cycles to run
pc.v.open_ms       = 600         # how long to keep each valve open
pc.v.gap_ms        = 300         # gap after closing before next valve
pc.v.cycle_gap_ms  = 1000        # extra pause between cycles

# ======= State machine =======
states = ["sequencer"]
events = ["tick", "session_timer"]
initial_state = "sequencer"

# Internal indices
pc.v._rep = 0
pc.v._i   = 0
pc.v._is_open = True  # next action is OPEN for the current valve

TAG = "#OLF:"

def _send_open(n):
    pc.print("{}o{}".format(TAG, int(n)))

def _send_close(n):
    pc.print("{}c{}".format(TAG, int(n)))

def sequencer(event):
    if event == "entry":
        # Kick off immediately
        pc.publish_event("tick")

    elif event == "tick":
        # Finished all repeats?
        if pc.v._rep >= pc.v.repeats:
            pc.print("SEQUENCE_DONE")
            pc.stop_framework()
            return

        v = pc.v.valves[pc.v._i]

        if pc.v._is_open:
            _send_open(v)
            pc.v._is_open = False
            pc.set_timer("tick", int(pc.v.open_ms))
        else:
            _send_close(v)
            pc.v._is_open = True

            # Advance to next valve / possibly next cycle
            pc.v._i += 1
            if pc.v._i >= len(pc.v.valves):
                pc.v._i = 0
                pc.v._rep += 1
                delay = int(pc.v.cycle_gap_ms)
            else:
                delay = int(pc.v.gap_ms)

            pc.set_timer("tick", delay)
