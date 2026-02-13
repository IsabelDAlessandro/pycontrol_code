# sync_beacon.py
# Reusable random sync pulse generator for pyControl tasks.
# Usage:
#   - define a Digital_output in hardware (e.g., photo_sync)
#   - in your task: events += ["sync_arm", "sync_off"]
#   - instantiate RandomSyncBeacon(dio=photo_sync, label="sync", mean_isi_ms=1500, pulse_ms=10)
#   - call sync.start() in run_start(), sync.stop() in run_end()
#   - call sync.handle(event) from all_states(event)

import pyControl.utility as pc
import math

class RandomSyncBeacon:
    def __init__(self, dio, label="sync", mean_isi_ms=1500, pulse_ms=10):
        """
        dio          : Digital_output instance (from hardware_definition)
        label        : string prefix for timer/event names (default 'sync')
        mean_isi_ms  : mean inter-pulse interval (Poisson) in ms
        pulse_ms     : pulse width (ms), line goes HIGH for this long
        """
        self.dio = dio
        self.label = label
        self.mean_isi_ms = int(mean_isi_ms)
        self.pulse_ms = int(pulse_ms)
        # timer event names (must be included in the task's events list)
        self.ev_arm = f"{label}_arm"
        self.ev_off = f"{label}_off"
        # optional published events (show up in TSV)
        self.ev_started = f"{label}_started"
        self.ev_stopped = f"{label}_stopped"
        self.ev_pulse = f"{label}_pulse"
        self.running = False

    def _next_isi_ms(self):
        # Exponential ISI: draw u in (0,1], isi = -mean * ln(u)
        u = max(1e-6, min(0.999999, pc.random()))  # avoid 0/1 edge cases
        return max(1, int(-self.mean_isi_ms * math.log(u)))

    def start(self):
        if self.running:
            return
        self.running = True
        pc.publish_event(self.ev_started)
        # schedule first arm
        pc.set_timer(self.ev_arm, self._next_isi_ms())

    def stop(self):
        if not self.running:
            return
        self.running = False
        # ensure line is low and disarm timers
        try:
            self.dio.off()
        except:
            pass
        pc.disarm_timer(self.ev_arm)
        pc.disarm_timer(self.ev_off)
        pc.publish_event(self.ev_stopped)

    def handle(self, event):
        """Call from all_states(event)."""
        if not self.running:
            return

        if event == self.ev_arm:
            # Raise line (pulse ON), log the pulse, schedule OFF
            self.dio.on()
            pc.publish_event(self.ev_pulse)
            pc.set_timer(self.ev_off, self.pulse_ms)

        elif event == self.ev_off:
            # Lower line (pulse OFF), schedule next arm
            self.dio.off()
            pc.set_timer(self.ev_arm, self._next_isi_ms())
