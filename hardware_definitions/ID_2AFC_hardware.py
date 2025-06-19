from devices import Breakout_1_2, Poke, Digital_output, Audio_board

board = Breakout_1_2()

# Nose-poke ports (12V Lee solenoids, from pyControl box pack)
right_port = Poke(board.port_2, rising_event="right_poke", falling_event="right_poke_out")
left_port = Poke(board.port_5, rising_event="left_poke", falling_event="left_poke_out")
center_port = Poke(board.port_4, rising_event="center_poke", falling_event="center_poke_out")
speaker = Audio_board(board.port_3)

# Odor valves (5V Lee solenoids from ID)
final_valve = Digital_output(pin=board.port_1.POW_C)
odor_A = Digital_output(pin=board.port_1.POW_A)
odor_B = Digital_output(pin=board.port_1.POW_B)