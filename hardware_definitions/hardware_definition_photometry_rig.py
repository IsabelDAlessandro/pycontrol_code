# hardware_definition.py

from devices import Breakout_1_2, Poke, Digital_output, Audio_board, Frame_logger
from pyControl.utility import set_timer, randint, publish_event

board = Breakout_1_2()

# IO (unchanged)
right_port      = Poke(board.port_2, rising_event="right_poke",  falling_event="right_poke_out")
left_port       = Poke(board.port_3, rising_event="left_poke",   falling_event="left_poke_out")
center_port     = Poke(board.port_6, rising_event="center_poke", falling_event="center_poke_out")

sync_out = Digital_output(pin=board.BNC_1)
#camera_out = Digital_output(pin=board.BNC_2)


#SYNC PULSE 
SYNC_PULSE_MS = 10
#CAM_PULSE_MS  = 10

ACQ_PULSE_MODE = "random"   # "fixed" or "random"
ACQ_INTERVAL_MS = 1000      # used if mode=="fixed"
ACQ_MIN_MS = 500            # used if mode=="random"
ACQ_MAX_MS = 1500           # used if mode=="random"

ACQ_SYNC_EVENT = "acq_sync_pulse"
#ACQ_CAM_EVENT  = "acq_cam_pulse"

def _olf(cmd: str) -> None:
    print(cmd)


# -----------------------
# Valve classes + helpers
# -----------------------
    
class OlfSerialValve:
    """Manifold valve: #OLF:oN / #OLF:cN"""
    def __init__(self, valve_num: int):
        self.valve_num = int(valve_num)

    def on(self) -> None:
        _olf(f"#OLF:o{self.valve_num}")

    def off(self) -> None:
        _olf(f"#OLF:c{self.valve_num}")

class FinalValveSerial:
    """Final valve: #OLF:t (on) / #OLF:x (off)"""
    def on(self) -> None:
        _olf("#OLF:a")

    def off(self) -> None:
        _olf("#OLF:x")


final_valve = FinalValveSerial()  # <-- use this in tasks instead of TTL if you want serial gating

_selected_odor_valves = []  # list[OlfSerialValve]

def set_odor_valves(valves):
    """
    valves can be:
      - int
      - list/tuple of int
      - list/tuple of OlfSerialValve
    """
    global _selected_odor_valves
    if valves is None:
        _selected_odor_valves = []
        return

    if isinstance(valves, int):
        valves = [valves]
    out = []
    for v in valves:
        if isinstance(v, OlfSerialValve):
            out.append(v)
        else:
            out.append(OlfSerialValve(int(v)))
    _selected_odor_valves = out

def enable_odor_valves():
    """Step 1: open selected odor valves (manifold)."""
    for v in _selected_odor_valves:
        v.on()

def disable_odor_valves():
    """Close selected odor valves (manifold)."""
    for v in _selected_odor_valves:
        v.off()

def final_on():
    """Step 2: open final valve (deliver)."""
    final_valve.on()

def final_off():
    """Step 3: close final valve (stop delivery)."""
    final_valve.off()

def stop_odor_delivery():
    """Convenience: stop final + close selected odor valves."""
    final_off()
    disable_odor_valves()


# -----------------------
# Acquisition (sync + camera)
# -----------------------
_acq_enabled = False

def _next_acq_interval_ms():
    if ACQ_PULSE_MODE == "fixed":
        return int(ACQ_INTERVAL_MS)
    # random in [min, max]
    return int(randint(ACQ_MIN_MS, ACQ_MAX_MS))

def start_acq_pulses(immediate=True):
    """
    Call from each task's run_start().
    Starts recurring sync+camera pulses, unrelated to odor timing.
    """
    global _acq_enabled
    _acq_enabled = True

    if immediate:
        # fire once at start (optional)
        sync_out.pulse(SYNC_PULSE_MS)
        #camera_out.pulse(CAM_PULSE_MS)

    # schedule first tick events
    dt = _next_acq_interval_ms()
    set_timer(ACQ_SYNC_EVENT, dt)
    #set_timer(ACQ_CAM_EVENT,  dt)

def stop_acq_pulses():
    """
    Call from each task's run_end().
    Stops future pulses (any already-scheduled timer event may still arrive once,
    but handler below will ignore when disabled).
    """
    global _acq_enabled
    _acq_enabled = False

def handle_acq_pulse_events(event):
    """
    Call from each task's all_states(event).
    When events fire, emits TTL pulses and reschedules itself.
    """
    if not _acq_enabled:
        return

    if event == ACQ_SYNC_EVENT:
        sync_out.pulse(SYNC_PULSE_MS)
        
        set_timer(ACQ_SYNC_EVENT, _next_acq_interval_ms())

    # elif event == ACQ_CAM_EVENT:
    #     camera_out.pulse(CAM_PULSE_MS)
        
    #     set_timer(ACQ_CAM_EVENT, _next_acq_interval_ms())

        
# Shared reward durations (if you export these here)
rwd_durations = [37, 37]
