import pyControl.utility as pc
from hardware_definition import (
    right_port,
    left_port,
    rwd_durations,
    start_acq_pulses,
    stop_acq_pulses,
    handle_acq_pulse_events,
    ACQ_SYNC_EVENT
)

# State machine
states = ["wait_for_poke", "left_reward", "right_reward", "inter_trial_interval"]

# Include acquisition beacon timer events so the framework will route them to all_states().
events = [
    "poke",
    "right_poke",
    "left_poke",
    "right_poke_out",
    "left_poke_out",
    "session_timer",
    ACQ_SYNC_EVENT
]

initial_state = "wait_for_poke"

# Parameters.
pc.v.session_duration = 0.5 * pc.hour  # Session duration.
pc.v.reward_durations = rwd_durations  # Reward delivery duration (ms) [left, right].
pc.v.ITI_duration = 1 * pc.second      # Inter trial interval duration.
pc.v.reward_dur_multiplier = 1         # adjust per mouse; increase if not interested
pc.v.max_rewards = 150

# Variables.
pc.v.n_rewards = 0  # Number of rewards obtained.


# These funcs are auto-run at beginning + end
def run_start():
    # Start acquisition beacons (sync + camera), independent of task logic.
    start_acq_pulses(immediate=True)

    # Set session timer.
    pc.set_timer("session_timer", pc.v.session_duration)


def run_end():
    # Stop acquisition beacons.
    stop_acq_pulses()

    # Turn off all hardware outputs.
    right_port.SOL.off()
    left_port.SOL.off()

    pc.print("SESSION_DONE")


### State behaviour functions ###

def wait_for_poke(event):
    if event == "right_poke":
        pc.goto_state("right_reward")
        pc.v.n_rewards += 1
    elif event == "left_poke":
        pc.goto_state("left_reward")
        pc.v.n_rewards += 1


def left_reward(event):
    # Deliver reward to left poke.
    if event == "entry":
        pc.timed_goto_state("inter_trial_interval", pc.v.reward_dur_multiplier * pc.v.reward_durations[0])
        left_port.SOL.on()
    elif event == "exit":
        left_port.SOL.off()


def right_reward(event):
    # Deliver reward to right poke.
    if event == "entry":
        pc.timed_goto_state("inter_trial_interval", pc.v.reward_dur_multiplier * pc.v.reward_durations[1])
        right_port.SOL.on()
    elif event == "exit":
        right_port.SOL.off()


def inter_trial_interval(event):
    # Go to init trial after specified delay.
    if event == "entry":
        if pc.v.n_rewards >= pc.v.max_rewards:
            pc.stop_framework()
        else:
            pc.timed_goto_state("wait_for_poke", pc.v.ITI_duration)


# State independent behaviour.
def all_states(event):
    # Handle acquisition beacon pulses (sync + camera).
    handle_acq_pulse_events(event)

    # When 'session_timer' event occurs stop framework to end session.
    if event == "session_timer":
        pc.stop_framework()
