import pyControl.utility as pc
from hardware_definition import right_port, left_port, center_port, final_valve, odor_A, odor_B

# -------- Params --------
pc.v.required_center_hold_duration = 500  # ms
pc.v.odor_delivery_duration        = 500  # ms
pc.v.ITI_duration                  = 1000 # ms
pc.v.timeout_duration              = 1000 # ms
pc.v.reward_durations              = [47, 54]  # [left, right] ms
pc.v.reward_duration_multiplier    = 1.25
pc.v.n_rewards                     = 0
pc.v.rewarded_side                 = "left"    # start side

# -------- State machine scaffold --------
states = [
    "inter_trial_interval",
    "wait_for_center_poke",
    "hold_center_poke",
    "deliver_odor",
    "wait_for_side_poke",
    "left_reward",
    "right_reward",
    "timeout",
]
events = [
    "center_poke", "center_poke_out",
    "left_poke", "left_poke_out",
    "right_poke", "right_poke_out",
    "session_timer",
]
initial_state = "inter_trial_interval"

# -------- Helpers --------
def _apply_odors_for_current_side():
    # Teensy serial wrappers (these print "#OLF:oN/#OLF:cN" to TSV; your bridge forwards)
    if pc.v.rewarded_side == "left":
        odor_B.off()
        odor_A.on()
    else:
        odor_A.off()
        odor_B.on()

def _cleanup_odors():
    odor_A.off()
    odor_B.off()

def is_rewarded(side):
    pc.v.choice = side
    if side == pc.v.rewarded_side:
        pc.v.outcome = 1
        pc.v.n_rewards += 1
        # flip side each trial just for testing
        pc.v.rewarded_side = "left" if (pc.v.rewarded_side == "right") else "right"
    else:
        pc.v.outcome = 0
    return pc.v.outcome

# -------- States --------
def inter_trial_interval(event):
    if event == "entry":
        # brief final-valve flush (open during ITI; close on exit)
        final_valve.on()
        pc.timed_goto_state("wait_for_center_poke", pc.v.ITI_duration)
    elif event == "exit":
        final_valve.off()

def wait_for_center_poke(event):
    if event == "entry":
        # set odors for next trial and cue light
        _apply_odors_for_current_side()
        center_port.LED.on()
    elif event == "center_poke":
        pc.goto_state("hold_center_poke")

def hold_center_poke(event):
    if event == "entry":
        pc.timed_goto_state("deliver_odor", pc.v.required_center_hold_duration)
    elif event == "center_poke_out":
        # didn’t hold long enough, try again
        pc.goto_state("wait_for_center_poke")

def deliver_odor(event):
    if event == "entry":
        center_port.LED.off()
        final_valve.on()
        pc.timed_goto_state("wait_for_side_poke", pc.v.odor_delivery_duration)
    elif event == "exit":
        # stop delivery; close odors so final valve flushes clean air
        final_valve.off()
        _cleanup_odors()

def wait_for_side_poke(event):
    if event == "left_poke":
        if is_rewarded("left"):
            pc.goto_state("left_reward")
        else:
            pc.goto_state("timeout")
    elif event == "right_poke":
        if is_rewarded("right"):
            pc.goto_state("right_reward")
        else:
            pc.goto_state("timeout")

def left_reward(event):
    if event == "entry":
        pc.timed_goto_state("inter_trial_interval",
                            pc.v.reward_duration_multiplier * pc.v.reward_durations[0])
        left_port.SOL.on()
    elif event == "exit":
        left_port.SOL.off()

def right_reward(event):
    if event == "entry":
        pc.timed_goto_state("inter_trial_interval",
                            pc.v.reward_duration_multiplier * pc.v.reward_durations[1])
        right_port.SOL.on()
    elif event == "exit":
        right_port.SOL.off()

def timeout(event):
    if event == "entry":
        pc.timed_goto_state("inter_trial_interval", pc.v.timeout_duration)

def run_end():
    # fail-safe cleanup
    right_port.SOL.off()
    left_port.SOL.off()
    center_port.LED.off()
    _cleanup_odors()
    final_valve.off()
