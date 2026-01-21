import pyControl.utility as pc
from hardware_definition import right_port, left_port, center_port, final_valve, odor_A, odor_B, thermistor_sync


# Rwd sizing
# For rwd durn multplier of 1, 1 mL ~ 125 rewards.
# For rwd durn multiplier of 0.75, ~ 225 rewards.
pc.v.reward_duration_multiplier = 0.75
pc.v.n_allowed_rwds = 200  # total per session


# Shaping vars
pc.v.required_center_hold_duration = 300

# Rewards-per-block function
# CHANGE ME based on demands of shaping
def get_n_rwds_allowed_in_block():
    # pc.v.n_allowed_rwds_per_block = 10  # initial high value for shaping (Day 1)
    # pc.v.n_allowed_rwds_per_block = 7  # Day 2
    # pc.v.n_allowed_rwds_per_block = 3  # Day 3
    pc.v.n_allowed_rwds_per_block = 2 if pc.withprob(0.5) else 3  # Day 4
    #pc.v.n_allowed_rwds_per_block = 2 if pc.withprob(0.5) else (1 if pc.withprob(0.5) else 3)  # Day 5


# Additional vars for blocks
pc.v.n_allowed_rwds_per_block = 3
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
    pc.publish_event("set_odor_valves_for_trial")


def check_update_rewarded_side():
    if pc.v.n_rewards_in_block >= pc.v.n_allowed_rwds_per_block:
        pc.v.rewarded_side = "left" if (pc.v.rewarded_side == "right") else "right"
        get_n_rwds_allowed_in_block()
        pc.v.n_rewards_in_block = 0
    return

def is_rewarded(side):
    pc.v.choice = side
    if side == pc.v.rewarded_side:
        pc.v.n_correct_trials += 1
        pc.v.n_rewards_in_block += 1
        pc.v.n_rewards += 1
        pc.v.outcome = 1
    else:
        pc.v.outcome = 0
    pc.v.ave_correct_tracker.add(pc.v.outcome)
    return pc.v.outcome

############
# All code below here is direct c/p from task 2, save for a few small changes (ie printing more vars)
############

# State machine
states = ["wait_for_center_poke", "deliver_odor", "wait_for_side_poke", "left_reward", "right_reward", "inter_trial_interval", "timeout"]
events = ["center_poke", "right_poke", "left_poke", "center_poke_out", "right_poke_out", "left_poke_out", "session_timer", "finish_ITI", "close_final_valve", "close_final_valve_done", "center_poke_held", "set_odor_valves_for_trial","therm_sync_ON"]
initial_state = "wait_for_center_poke"

# Odor parameters
pc.v.odor_delivery_duration = 500
pc.v.final_valve_flush_duration = 500  # ensure this is shorter than the ITI

# General Parameters.
pc.v.session_duration = 1 * pc.hour  # Session duration.
pc.v.reward_durations = [47, 54]  # Reward delivery duration (ms) [left, right].
pc.v.rewarded_side = "left" if (pc.random() > 0.5) else "right"

pc.v.ITI_duration = 3 * pc.second  # Inter trial interval duration. Ensure this is longer than final valve flush duration.
pc.v.timeout_duration = 2 * pc.second  # timeout for wrong trials (in addition to ITI)

# Variables.
pc.v.entry_time = 0
pc.v.n_total_trials = 0
pc.v.n_early_errors = 0
pc.v.mov_ave_correct = 0  # moving avg of last 10 trials
pc.v.overall_ave_correct = 0  # excludes early errs

# Reward variables (updated / used in "is_rewarded")
pc.v.choice = "right"
pc.v.outcome = 0
pc.v.n_correct_trials = 0
pc.v.n_rewards = 0  # total number of rewards obtained.
pc.v.ave_correct_tracker = pc.OnlineMovingAverage(10)
 

### These funcs are auto-run at beginning + end ###
def run_start():
    # Set session timer and turn on houslight.
    pc.set_timer("session_timer", pc.v.session_duration)
    pc.publish_event("set_odor_valves_for_trial")

def run_end():
    # Turn off all hardware outputs.
    right_port.SOL.off()
    left_port.SOL.off()
    center_port.LED.off()
    disable_odor_valves()
    pc.print("SESSION_DONE")
    # Do whatever else...save data maybe?
    pass


# State-independent behaviour.
def all_states(event):
    # When 'session_timer' event occurs stop framework to end session.
    if event == "session_timer":
        pc.stop_framework()

    # End flushing of final valve
    elif event == "close_final_valve":
        final_valve.off()

    # After new trial's odor is selected in ITI, set the odor valves
    # so there is enough time for the odor to flow thru the tubes.
    # Importantly, we make sure the final valve is closed (200 ms
    # after the "off" command [just picked this number arbitrarily, could time it])
    # so that the next trial's odor doesn't accidentally leak out.
    elif event == "set_odor_valves_for_trial":
        if pc.timer_remaining("close_final_valve_done") == 0:
            set_odor_valves()
        else:
            pc.set_timer("set_odor_valves_for_trial", 100)


### State-machine ###

def wait_for_center_poke(event):

    if event == "entry":
        center_port.LED.on()  # cues mouse that trial is available
        pc.v.entry_time = pc.get_current_time()  # start early-error buffer
        # set_odor_valves()  # replaced by all_states logic
    
    # If mouse pokes either side port *after* the early-error buffer
    # has elapsed, then timeout and restart the trial.
    elif (
        ((pc.get_current_time() - pc.v.entry_time) > 300)
        and (event == "left_poke" or event == "right_poke")
    ):
        center_port.LED.off()
        disable_odor_valves()
        pc.v.n_early_errors += 1
        pc.goto_state("timeout")

    # If ms is still licking at reward port, then restart the 
    # early-error buffer when it leaves the side port.
    elif (event == "left_poke_out" or event == "right_poke_out"):
        pc.v.entry_time = pc.get_current_time()

    # Require mouse to hold nose in center port for a certain amt of time.
    # If it does not, it's not an error, just nothing happens.
    elif event == "center_poke":
        pc.set_timer("center_poke_held", pc.v.required_center_hold_duration)
    elif event == "center_poke_out":
        pc.disarm_timer("center_poke_held")
    elif event == "center_poke_held":
        pc.goto_state("deliver_odor")


def deliver_odor(event):
    if event == "entry":
        center_port.LED.off()  # the light turning off will cue the mouse to the timing of odor delivery
        final_valve.on()  # delivers the odor!
        pc.timed_goto_state("wait_for_side_poke", pc.v.odor_delivery_duration)
    elif event == "exit":
        disable_odor_valves()  # close the odor valves to allow final valve to flush w clean air
        pc.set_timer("close_final_valve", (pc.v.final_valve_flush_duration))  # this will close the final valve after flush
        pc.set_timer("close_final_valve_done", (pc.v.final_valve_flush_duration + 200))  # this allows buffer time for final valve to close before switching odor valves on again


def wait_for_side_poke(event):
    if event == "right_poke":
        if is_rewarded("right"):
            pc.goto_state("right_reward")
        else:
            pc.goto_state("timeout")

    elif event == "left_poke":
        if is_rewarded("left"):
            pc.goto_state("left_reward")
        else:
            pc.goto_state("timeout")


def left_reward(event):
    # Deliver reward to left poke.
    if event == "entry":
        pc.timed_goto_state("inter_trial_interval", pc.v.reward_duration_multiplier * pc.v.reward_durations[0])
        left_port.SOL.on()
    elif event == "exit":
        left_port.SOL.off()


def right_reward(event):
    # Deliver reward to right poke.
    if event == "entry":
        pc.timed_goto_state("inter_trial_interval", pc.v.reward_duration_multiplier * pc.v.reward_durations[1])
        right_port.SOL.on()
    elif event == "exit":
        right_port.SOL.off()


def timeout(event):
    if event == "entry":
        pc.timed_goto_state("inter_trial_interval", pc.v.timeout_duration)


def inter_trial_interval(event):
    if event == "entry":
         
        # Start ITI timer. Using a timer instead of "timed_goto_state()"
        # allows us to reset the timer if mouse isn't finished licking 
        # the reward, without having to restart the entire ITI state, 
        # which would require lots of flags to only update things once, 
        # and would be generally confusing.
        pc.set_timer("finish_ITI", pc.v.ITI_duration)
        pc.v.entry_time = pc.get_current_time()

        # Update vars
        pc.v.n_total_trials += 1
        pc.v.mov_ave_correct = pc.v.ave_correct_tracker.ave
        pc.v.overall_ave_correct = pc.v.n_correct_trials / max(pc.v.n_total_trials - pc.v.n_early_errors, 1)
        pc.print_variables(["n_total_trials", "n_correct_trials", "n_early_errors", "mov_ave_correct", "overall_ave_correct", "rewarded_side", "choice", "outcome"])

        # Auto-increase center hold duration for shaping
        if (
            ((pc.v.n_rewards == 25) or (pc.v.n_rewards == 50))
            and (pc.v.required_center_hold_duration < 300)
        ):
            pc.v.required_center_hold_duration += 75

        # Do any other required ITI logic in this function
        do_other_ITI_logic()
    
    # If mouse is still licking the reward, let it keep going until it's done.
    elif (
        pc.v.outcome
        and (
                ((event == "left_poke") and pc.v.choice == "left")
                or ((event == "right_poke") and pc.v.choice == "right")
            )
        and ((pc.get_current_time() - pc.v.entry_time) < (pc.v.ITI_duration/2))
    ):
        pc.reset_timer("finish_ITI", pc.v.ITI_duration)

    # Once ITI finishes, go to first state again.
    elif event == "finish_ITI":
        pc.goto_state("wait_for_center_poke")
    
    # Check if we need to stop task for any reason.
    elif event == "exit":
        if pc.v.n_rewards >= pc.v.n_allowed_rwds:
            pc.stop_framework()