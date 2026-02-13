# simple_valve_sequence_generic.py
# Cycles through a list of valves with clean timing using the OLF bridge.
# Commands printed:
#   "#OLF:oN" -> open manifold valve N
#   "#OLF:cN" -> close manifold valve N
#   "#OLF:t"  -> final valve ON
#   "#OLF:x"  -> final valve OFF
from hardware_definition import sync_out, SYNC_MIN_MS, SYNC_MAX_MS, SYNC_PULSE_MS
import pyControl.utility as pc

# =======================
# ====== CONFIG =========
# =======================

# Valves to test, in order:
pc.v.valve_seq = [1, 2, 3]

# How many full passes through valve_seq
pc.v.repeats = 3

# Timing (milliseconds)
pc.v.flush_before_final_ms = 1000   # prefill time between oN and final ON
pc.v.final_on_ms           = 2000   # time the final valve stays ON
pc.v.inter_valve_gap_ms    = 5000  # gap after closing before moving to next valve

# =======================
# ====== HELPERS ========
# =======================

def olf_open(n):
    pc.print("#OLF:o{}".format(int(n)))

def olf_close(n):
    pc.print("#OLF:c{}".format(int(n)))

def final_on():
    pc.print("#OLF:t")

def final_off():
    pc.print("#OLF:x")

def _total_cycles():
    return len(pc.v.valve_seq) * pc.v.repeats

def _current_valve():
    # Which valve for the current cycle index
    idx_in_seq = pc.v.cycle_idx % len(pc.v.valve_seq)
    return pc.v.valve_seq[idx_in_seq]

# =======================
# ===== STATE SETUP =====
# =======================

states = [
    "bootstrap",          # one-shot start
    "open_valve",         # print #OLF:oN
    "prefill_wait",       # wait flush_before_final_ms
    "final_on_state",     # print #OLF:t and wait final_on_ms
    "final_off_and_close",# print #OLF:x and #OLF:cN, then wait inter_valve_gap_ms
    "advance_or_done",    # increment index or finish
    "done",               # stop framework
]

events = [
    "kick",               # 1 ms deferral event
    "prefill_done",
    "final_on_done",
    "gap_done",
    "sync_tick",
    "sync_pulse"
]

def _sync_next_interval():
    # random int in [SYNC_MIN_MS, SYNC_MAX_MS]
    return int(SYNC_MIN_MS + pc.random() * (SYNC_MAX_MS - SYNC_MIN_MS))

initial_state = "bootstrap"

# =======================
# ===== RUN HOOKS  ======
# =======================

def run_start():
    pc.set_timer("sync_tick", _sync_next_interval())
    # Initialize counters and defer first step
    pc.v.cycle_idx = 0   # 0 .. _total_cycles()-1
    pc.set_timer("kick", 1)
    

def run_end():
    # Nothing to shut down here (bridge-only commands), but it's fine to be explicit
    final_off()
    pc.disarm_timer("sync_tick") 

# =======================
# ===== STATE LOGIC =====
# =======================

def all_states(event):
    # ... your existing handlers ...
    if event == "sync_tick":
        # Drive the physical TTL
        sync_out.pulse(SYNC_PULSE_MS)
        # Also log a labeled event to the .tsv
        pc.publish_event("sync_pulse")
        # Schedule the next random pulse
        pc.set_timer("sync_tick", _sync_next_interval())

def bootstrap(event):
    if event == "kick":
        if _total_cycles() == 0:
            pc.goto_state("done")
        else:
            pc.goto_state("open_valve")

def open_valve(event):
    if event == "entry":
        v = _current_valve()
        olf_open(v)
        # Defer transition out of "entry"
        pc.set_timer("prefill_done", pc.v.flush_before_final_ms)
    elif event == "prefill_done":
        pc.goto_state("final_on_state")

def prefill_wait(event):
    # (Unused in this simplified pattern, kept for clarity if you split states)
    pass

def final_on_state(event):
    if event == "entry":
        final_on()
        pc.set_timer("final_on_done", pc.v.final_on_ms)
    elif event == "final_on_done":
        pc.goto_state("final_off_and_close")

def final_off_and_close(event):
    if event == "entry":
        v = _current_valve()
        final_off()
        olf_close(v)
        pc.set_timer("gap_done", pc.v.inter_valve_gap_ms)
    elif event == "gap_done":
        pc.goto_state("advance_or_done")

def advance_or_done(event):
    if event == "entry":
        # Defer decision out of 'entry'
        pc.set_timer("kick", 1)
    elif event == "kick":
        pc.v.cycle_idx += 1
        if pc.v.cycle_idx >= _total_cycles():
            pc.goto_state("done")
        else:
            pc.goto_state("open_valve")

def done(event):
    if event == "entry":
        pc.print("SEQUENCE_COMPLETE")
        pc.stop_framework()
