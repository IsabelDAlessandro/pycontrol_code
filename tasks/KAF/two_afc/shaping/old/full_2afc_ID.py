
import pyControl.utility as pc
from hardware_definition import right_port, left_port, center_port, final_valve, odor_A, odor_B, rwd_durations

# ---------------------------- VARIABLES TO EDIT -------------------------------
pc.v.required_center_hold_duration = 300
pc.v.n_allowed_rwds = 200
pc.right_odor_valve = 1
pc.left_odor_valve = 2
# -----------------------------------------------------------------------------

# =======================
# ===== CONFIG ==========
# =======================

pc.v.choice_window_ms            = 5000 ## what is this?
pc.v.odor_delivery_duration      = 500     # ms final valve ON before choice
pc.v.final_valve_flush_duration  = 1000    # ms TTL close delay to flush
pc.v.session_duration            = 1 * pc.hour
pc.v.reward_durations            = rwd_durations
pc.v.ITI_duration                = 3 * pc.second
pc.v.timeout_early_ms            = 500
pc.v.timeout_wrong_ms            = 2000
pc.v.early_error_buffer_duration = 300

# =======================
# ===== VARIABLES =======
# =======================

pc.v.entry_time        = 0
pc.v.n_total_trials    = 0
pc.v.n_early_errors    = 0
pc.v.n_correct_trials  = 0
pc.v.n_rewards         = 0
pc.v.choice            = "none"
pc.v.rewarded_side     = "right" #change this or does it get switched?
pc.v.current_odor      = None
pc.v.odor_preset_done  = False
pc.v.outcome           = 0

# =======================
# ===== ODOR LOGIC ======
# =======================

def set_odor_valves():
    """
    Preset odor valves for the upcoming trial.
    A and B are defined as OlfSerialValve objects that print "#OLF:oN" when .on() is called.
    """
    odor_A.off()
    odor_B.off()

    if pc.v.current_odor == 'A':
        pc.v.rewarded_side = "right"
        odor_A.set_valve(pc.right_odor_valve)
        odor_A.on()
    elif pc.v.current_odor == 'B':
        pc.v.rewarded_side = "left"
        odor_B.set_valve(pc.left_odor_valve)   
        odor_B.on()

def disable_odor_valves():
    odor_A.off()
    odor_B.off()
    pc.v.current_odor = None

# ===========================
# ===== TRIAL LOGIC   =======
# ===========================

def select_next_trial():
    # 50/50 choose next odor; mapping fixed (A->right, B->left)
    pc.v.current_odor = 'A' if pc.withprob(0.5) else 'B'
    pc.publish_event("set_odor_valves_for_trial")

def is_rewarded(side):
    pc.v.choice = side
    correct = (side == pc.v.rewarded_side)
    pc.v.outcome = 1 if correct else 0
    if correct:
        pc.v.n_correct_trials += 1
        pc.v.n_rewards += 1
    return correct

# =======================
# ===== STATE SETUP =====
# =======================

states = [
    "wait_for_center_poke",
    "deliver_odor",
    "wait_for_side_poke",
    "left_reward",
    "right_reward",
    "inter_trial_interval",
    "timeout",
]

events = [
    "center_poke", "right_poke", "left_poke",
    "center_poke_out", "right_poke_out", "left_poke_out",
    "session_timer", "finish_ITI",
    "close_final_valve", "close_final_valve_done",
    "center_poke_held",
    "set_odor_valves_for_trial",
    "choice_window_over", "svf_recheck"
]

initial_state = "wait_for_center_poke"

# =======================
# ===== RUN HOOKS  ======
# =======================

def run_start():
    final_valve.off()
    pc.v.odor_preset_done = False
    pc.set_timer("session_timer", pc.v.session_duration)
    select_next_trial()  
def run_end():
    right_port.SOL.off()
    left_port.SOL.off()
    center_port.LED.off()
    disable_odor_valves()
    pc.print("SESSION_DONE")

# =======================
# ===== HELPERS    ======
# =======================

def _rwd_ms(side_index):
    return int(pc.v.reward_durations[side_index])

def all_states(event):
    if event == "session_timer":
        pc.stop_framework()

    elif event == "close_final_valve":
        final_valve.off()

    # After selecting next trial during ITI, preset odor once final valve is closed.
    elif event == "set_odor_valves_for_trial":
        if pc.timer_remaining("close_final_valve_done") == 0 and not pc.v.odor_preset_done:
            set_odor_valves()
            pc.v.odor_preset_done = True
        elif not pc.v.odor_preset_done:
            pc.set_timer("svf_recheck", 50)

    elif event == "svf_recheck":
        if pc.timer_remaining("close_final_valve_done") == 0 and not pc.v.odor_preset_done:
            set_odor_valves()
            pc.v.odor_preset_done = True
        elif not pc.v.odor_preset_done:
            pc.reset_timer("svf_recheck", 50)

# =======================
# ===== STATES      =====
# =======================

def wait_for_center_poke(event):
    if event == "entry":
        center_port.LED.on()
        pc.v.entry_time = pc.get_current_time()

    elif (
        ((pc.get_current_time() - pc.v.entry_time) > pc.v.early_error_buffer_duration)
        and (event == "left_poke" or event == "right_poke")
    ):
        center_port.LED.off()
        disable_odor_valves()
        pc.v.n_early_errors += 1
        pc.goto_state("timeout")
        pc.v.timeout_duration = pc.v.timeout_early_ms

    elif (event == "left_poke_out" or event == "right_poke_out"):
        pc.v.entry_time = pc.get_current_time()

    elif event == "center_poke":
        pc.set_timer("center_poke_held", pc.v.required_center_hold_duration)
    elif event == "center_poke_out":
        pc.disarm_timer("center_poke_held")
    elif event == "center_poke_held":
        pc.goto_state("deliver_odor")

def deliver_odor(event):
    if event == "entry":
        center_port.LED.off()
        final_valve.on()
        pc.timed_goto_state("wait_for_side_poke", pc.v.odor_delivery_duration)

    elif event == "exit":
        disable_odor_valves()
        pc.set_timer("close_final_valve", pc.v.final_valve_flush_duration)
        pc.set_timer("close_final_valve_done", pc.v.final_valve_flush_duration + 200)

def wait_for_side_poke(event):
    if event == "entry":
        if pc.v.choice_window_ms > 0:
            pc.set_timer("choice_window_over", pc.v.choice_window_ms)

    if event == "right_poke":
        if is_rewarded("right"):
            pc.goto_state("right_reward")
        else:
            pc.v.timeout_duration = pc.v.timeout_wrong_ms
            pc.goto_state("timeout")

    elif event == "left_poke":
        if is_rewarded("left"):
            pc.goto_state("left_reward")
        else:
            pc.v.timeout_duration = pc.v.timeout_wrong_ms
            pc.goto_state("timeout")

    elif event == "choice_window_over":
        pc.v.outcome = 0
        pc.goto_state("inter_trial_interval")

def left_reward(event):
    if event == "entry":
        left_port.SOL.on()
        pc.timed_goto_state("inter_trial_interval", _rwd_ms(0))
    elif event == "exit":
        left_port.SOL.off()

def right_reward(event):
    if event == "entry":
        right_port.SOL.on()
        pc.timed_goto_state("inter_trial_interval", _rwd_ms(1))
    elif event == "exit":
        right_port.SOL.off()

def timeout(event):
    if event == "entry":
        pc.timed_goto_state("inter_trial_interval", pc.v.timeout_duration)

def inter_trial_interval(event):
    if event == "entry":
        pc.set_timer("finish_ITI", pc.v.ITI_duration)
        pc.v.entry_time = pc.get_current_time()

        pc.v.n_total_trials += 1
        pc.print_variables([
            "n_total_trials", "n_correct_trials",
            "rewarded_side", "choice", "outcome"
        ])

        pc.v.odor_preset_done = False
        select_next_trial()

    elif event == "finish_ITI":
        pc.goto_state("wait_for_center_poke")

    elif event == "exit":
        if pc.v.n_rewards >= pc.v.n_allowed_rwds:
            pc.stop_framework()
