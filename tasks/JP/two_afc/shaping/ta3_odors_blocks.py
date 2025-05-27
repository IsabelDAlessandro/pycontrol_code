import pyControl.utility as pc
from pyControl.tasks.JP.two_afc.shaping.t2_center_poke_either_side import *


# Additional vars for blocks
pc.v.n_allowed_rwds_per_block = 10
pc.v.n_rewards_in_block = 0  # per-block counter

# Re-define these functions here to produce odor behavior
def set_odor_valves():
    if pc.v.rewarded_side == "left":
        odor_B.off()
        odor_A.on()
    elif pc.v.rewarded_side == "right":
        odor_A.off()
        odor_B.on()

def disable_odor_valves():
    odor_A.off()
    odor_B.off()



### Helper functions for rwds ###

def do_other_ITI_logic():
    check_update_rewarded_side()


def check_update_rewarded_side():
    if pc.v.n_rewards_in_block >= pc.v.n_allowed_rwds_per_block:
        pc.v.rewarded_side = "left" if (pc.v.rewarded_side == "right") else "right"
        pc.v.n_rewards_in_block = 0
    return

def is_rewarded(side):
    pc.v.choice = side
    if side == pc.v.rewarded_side:
        pc.v.n_correct_trials += 1
        pc.v.n_rewards_in_block += 1
        pc.v.outcome = 1
    else:
        pc.v.outcome = 0
    pc.v.ave_correct_tracker.add(pc.v.outcome)
    return pc.v.outcome
