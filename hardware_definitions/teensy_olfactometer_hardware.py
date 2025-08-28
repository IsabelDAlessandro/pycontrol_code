# Teensy olfactometer wiring for pyControl
# - final_valve is a TTL output pin that goes to the Teensy's "final valve gate" BNC
# - odor_A / odor_B are wrappers that emit '#OLF:' lines to the session TSV,
#   which olf_bridge_tail.py forwards to the Teensy over COM5.

from devices import Breakout_1_2, Poke, Digital_output, Audio_board, Frame_logger

board = Breakout_1_2()

# Nose-poke ports / audio / sync (unchanged)
right_port      = Poke(board.port_2, rising_event="right_poke",  falling_event="right_poke_out")
left_port       = Poke(board.port_5, rising_event="left_poke",   falling_event="left_poke_out")
center_port     = Poke(board.port_6, rising_event="center_poke", falling_event="center_poke_out")
speaker         = Audio_board(board.port_3)
thermistor_sync = Frame_logger(pin=board.BNC_1,        rising_event="therm_sync_ON")
camera_sync     = Frame_logger(pin=board.port_4.DIO_A, rising_event="cam_ON")

# Final valve TTL to Teensy (BNC -> BNC cable). BNC_2 is a digital output.
final_valve = Digital_output(pin=board.BNC_2)

# ---- Serial-bridge "valve" wrappers ----
# These mimic Digital_output(.on/.off) but actually print tags that the TSV bridge forwards to Teensy.

class OlfSerialValve:
    def __init__(self, fixed_valve_num=None):
        # if fixed_valve_num is None, you can set it later via .set_valve(n)
        self.valve_num = fixed_valve_num

    def set_valve(self, n):
        # no type annotations for MicroPython compatibility
        self.valve_num = int(n)

    def on(self):
        # open the selected odor valve to prefill the line
        if self.valve_num is None:
            return
        print("#OLF:o{}".format(self.valve_num))

    def off(self):
        # close the selected odor valve (switch to blank)
        if self.valve_num is None:
            return
        print("#OLF:c{}".format(self.valve_num))

# A is fixed (edit this number to your A manifold valve)
odor_A = OlfSerialValve(fixed_valve_num=2)

# B is variable; you will set odor_B.set_valve(<n>) from the task before calling odor_B.on()
odor_B = OlfSerialValve()
