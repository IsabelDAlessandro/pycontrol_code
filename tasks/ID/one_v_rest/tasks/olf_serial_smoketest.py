# olf_serial_ttl_sequence_test.py
# Sequence:
# o1 -> (2s) -> final ON -> (2s) -> final OFF -> c1 -> (5s) ->
# o2 -> (2s) -> final ON -> (2s) -> final OFF -> c2 -> end

from pyControl.utility import *


from hardware_definition import (final_valve) #BNC_2 TTL

# --- Timings (ms) ---
v.start_delay_ms    = 1000   # give the TSV bridge a moment to attach
v.prefill_ms        = 2000   # wait after opening odor before final valve
v.final_open_ms     = 2000   # final valve HIGH duration
v.between_odors_ms  = 5000   # gap between odor 1 and odor 2

states = ['seq']
events = [
    'open1', 'open_final1', 'close_final1', 'close1',
    'open2', 'open_final2', 'close_final2', 'close2',
    'finish'
]
initial_state = 'seq'

def run_start():
    final_valve.off()  # safety: ensure TTL is low at start

def seq(event):
    if event == 'entry':
        set_timer('open1', v.start_delay_ms)

    elif event == 'open1':
        print("#OLF:o1")
        set_timer('open_final1', v.prefill_ms)

    elif event == 'open_final1':
        final_valve.on()
        set_timer('close_final1', v.final_open_ms)

    elif event == 'close_final1':
        final_valve.off()
        set_timer('close1', 1)

    elif event == 'close1':
        print("#OLF:c1")
        set_timer('open2', v.between_odors_ms)

    elif event == 'open2':
        print("#OLF:o2")
        set_timer('open_final2', v.prefill_ms)

    elif event == 'open_final2':
        final_valve.on()
        set_timer('close_final2', v.final_open_ms)

    elif event == 'close_final2':
        final_valve.off()
        set_timer('close2', 1)

    elif event == 'close2':
        print("#OLF:c2")
        set_timer('finish', 250)

    elif event == 'finish':
        stop_framework()
        print("SESSION_DONE")
