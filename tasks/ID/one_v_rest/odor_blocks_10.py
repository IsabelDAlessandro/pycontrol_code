# t3_a_odors_blocks_10.py
# 2AFC with Teensy olfactometer:
# - Odor selection via serial (#OLF: tags -> forwarded by olf_bridge_tail.py to Teensy)
# - Final valve gated by pyControl TTL on BNC_2 (wired to Teensy TTL-IN)
#
# Requires hardware_definition_teensy.py providing:
#   right_port, left_port, center_port, speaker
#   final_valve (Digital_output on board.BNC_2)
#   odor_A (fixed valve wrapper with .on()/.off())
#   odor_B (wrapper with .set_valve(n), .on()/.off())
#   thermistor_sync, camera_sync  (camera on board.port_4.DIO_A)

import pyControl.utility as pc
from teensy_olfactometer_hardware import (
    right_port, left_port, center_port, speaker,
    final_valve, odor_A, odor_B, thermistor_sync, camera_sync
)

# =====================
# ===== SETTINGS ======
# =====================

# Reward sizing (ms)
pc.v.reward_duration_ms_left   = 30
pc.v.reward_duration_ms_right  = 30
pc.v.reward_duration_multiplier = 0.75  # keep your calibration
pc.v.n_allowed_rwds = 150               # session cap

# Odor timing (ms)
pc.v.required_center_hold_duration = 300   # hold before enabling delivery
pc.v.odor_prefill_lead_ms          = 500   # prefill lead time
pc.v.final_valve_open_ms           = 250   # TTL HIGH window (odor delivery)
pc.v.post_final_close_odor_ms      = 100   # close odor line shortly after final valve closes

# ITI (ms)
pc.v.ITI_min = 1500
pc.v.ITI_max = 2500

# Trial/block logic
pc.v.block_size = 10                       # "blocks_10"
pc.v.B_candidates = [3,4,5,6,7,8]          # EDIT to your manifold mapping
pc.v.A_is_left_in_block = True             # block rule: True => A rewarded on left

# Counters / state vars
pc.v.trial_num = 0
pc.v.block_trial_idx = 0
pc.v.n_rewards = 0
pc.v.n_correct_trials = 0
pc.v.choice = None
pc.v.rewarded_side = None
pc.v.outcome = 0  # 1 correct / 0 incorrect
pc.v.current_stim = None        # 'A' or 'B'
pc.v.B_current_valve = None     # int, set when B chosen

# =========================
# ====== STATES & EVENTS ==
# =========================

states = [
    'wait_for_center_poke',
    'center_hold',
    'deliver_odor_and_enable_choice',
    'wait_for_choice',
    'left_reward',
    'right_reward',
    'ITI',
]

events = [
    'left_poke', 'left_poke_out',
    'right_poke', 'right_poke_out',
    'center_poke', 'center_poke_out',
    'finish_center_hold',
    'finish_final_valve',
    'close_odor_after_final',
    'finish_ITI',
]

initial_state = 'wait_for_center_poke'

# =========================
# ====== HELPERS ==========
# =========================

def rand_ITI():
    return pc.rnd(pc.v.ITI_min, pc.v.ITI_max)

def next_block_rule():
    """Flip which side is rewarded in the next block."""
    pc.v.A_is_left_in_block = not pc.v.A_is_left_in_block
    pc.v.block_trial_idx = 0

def pick_B_for_next_trial():
    """Choose Teensy valve for odor B and program the wrapper."""
    pc.v.B_current_valve = pc.choice(pc.v.B_candidates)
    odor_B.set_valve(pc.v.B_current_valve)

def choose_trial_stim_and_side():
    """Select stim and rewarded side for this trial."""
    pc.v.rewarded_side = 'left' if pc.v.A_is_left_in_block else 'right'
    pc.v.current_stim = pc.choice(['A', 'B'])
    if pc.v.current_stim == 'B':
        pick_B_for_next_trial()
    pc.v.block_trial_idx += 1
    if pc.v.block_trial_idx >= pc.v.block_size:
        next_block_rule()

def prefill_selected_odor():
    """Turn on the selected odor line to prefill tubing."""
    if pc.v.current_stim == 'A':
        odor_B.off()
        odor_A.on()
    else:
        odor_A.off()
        odor_B.on()

def stop_all_odors():
    """Close whichever odor was on (safe to call both)."""
    odor_A.off()
    odor_B.off()

def open_final_valve_TTL():
    final_valve.on()

def close_final_valve_TTL():
    final_valve.off()

def score_choice(chosen_side) -> bool:
    """Update metrics and return True if rewarded."""
    pc.v.choice = chosen_side
    correct_side = pc.v.rewarded_side
    pc.v.outcome = int(chosen_side == correct_side)
    if pc.v.outcome:
        pc.v.n_correct_trials += 1
        pc.v.n_rewards += 1
        return True
    return False

# =========================
# ====== RUN HOOKS ========
# =========================

def run_start():
    # any session init (e.g., timers) can go here
    pass

# =========================
# ====== STATE DEFS =======
# =========================

def wait_for_center_poke(event):
    if event == 'entry':
        pc.v.trial_num += 1
        choose_trial_stim_and_side()
        prefill_selected_odor()
        # allow prefill to advance before we require center hold
        pc.timed_goto_state('center_hold', pc.v.odor_prefill_lead_ms)

def center_hold(event):
    if event == 'entry':
        pc.set_timer('finish_center_hold', pc.v.required_center_hold_duration)
    elif event == 'center_poke_out':
        pc.cancel_timer('finish_center_hold')
        pc.goto_state('wait_for_center_poke')
    elif event == 'finish_center_hold':
        pc.goto_state('deliver_odor_and_enable_choice')

def deliver_odor_and_enable_choice(event):
    if event == 'entry':
        open_final_valve_TTL()
        pc.set_timer('finish_final_valve', pc.v.final_valve_open_ms)
    elif event == 'finish_final_valve':
        close_final_valve_TTL()
        pc.set_timer('close_odor_after_final', pc.v.post_final_close_odor_ms)
        pc.goto_state('wait_for_choice')

def wait_for_choice(event):
    if event == 'close_odor_after_final':
        stop_all_odors()

    if event == 'left_poke':
        if score_choice('left'):
            pc.goto_state('left_reward')
        else:
            pc.goto_state('ITI')

    elif event == 'right_poke':
        if score_choice('right'):
            pc.goto_state('right_reward')
        else:
            pc.goto_state('ITI')

def left_reward(event):
    # Deliver water to the LEFT using your existing solenoid lines
    if event == 'entry':
        dur = int(pc.v.reward_duration_ms_left * pc.v.reward_duration_multiplier)
        left_port.SOL.on()
        pc.timed_goto_state('ITI', dur)
    elif event == 'exit':
        left_port.SOL.off()

def right_reward(event):
    # Deliver water to the RIGHT using your existing solenoid lines
    if event == 'entry':
        dur = int(pc.v.reward_duration_ms_right * pc.v.reward_duration_multiplier)
        right_port.SOL.on()
        pc.timed_goto_state('ITI', dur)
    elif event == 'exit':
        right_port.SOL.off()

def ITI(event):
    if event == 'entry':
        close_final_valve_TTL()
        stop_all_odors()
        pc.set_timer('finish_ITI', rand_ITI())

    elif (
        event in ('left_poke', 'right_poke') and
        pc.time_in_state() < (pc.get_state_timer('finish_ITI') / 2)
    ):
        # optional: extend ITI if they poke early
        pc.reset_timer('finish_ITI', rand_ITI())

    elif event == 'finish_ITI':
        if pc.v.n_rewards >= pc.v.n_allowed_rwds:
            pc.stop_framework()
        else:
            pc.goto_state('wait_for_center_poke')
