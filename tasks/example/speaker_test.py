import pyControl.utility as pc
from hardware_definition import speaker

# --- Global Parameters ---
# Frequencies for the two tones in Hz
TONE_FREQ_1 = 5000 # As per your original code
TONE_FREQ_2 = 2000 # Example frequency for the second tone

# Durations for tone ON and speaker OFF periods
# Each tone is ON for 0.5s, followed by 0.5s silence.
# This makes a full cycle (Tone1_on -> Silence -> Tone2_on -> Silence) exactly 2 seconds long.
TONE_ON_DURATION = 0.5 * pc.second
SPEAKER_OFF_DURATION = 0.5 * pc.second

# --- States and Events ---
states = [
    "Initial_Silence",     # Optional: A state for an initial pause before the first tone
    "Tone1_on",            # State for playing Tone 1
    "Silence_after_Tone1", # State for brief silence after Tone 1
    "Tone2_on",            # State for playing Tone 2
    "Silence_after_Tone2"  # State for brief silence after Tone 2, cycles back to Tone 1
]

# No custom events are needed for this simple timed sequence,
# as transitions are handled by timed_goto_state.
events = []

# Define the initial state of the experiment
# This will start with a short silence before the tone sequence begins.
initial_state = "Initial_Silence"

# --- State Behaviour Functions ---

def Initial_Silence(event):
    """
    Handles the initial silence period before the first tone plays.
    This state allows for a moment of quiet before the auditory stimulus begins.
    """
    if event == "entry":
        # Changed from pc.printx to print for compatibility
        # Schedule transition to the first tone state after the initial silence duration.
        pc.timed_goto_state("Tone1_on", SPEAKER_OFF_DURATION)
    elif event == "exit":
        # No specific action needed when exiting this state.
        pass

def Tone1_on(event):
    """
    Plays Tone 1 for a specified duration and then transitions to a silence state.
    """
    if event == "entry":
        # Changed from pc.printx to print for compatibility
        speaker.sine(TONE_FREQ_1) # Start playing Tone 1
        # Schedule transition to the silence state that follows Tone 1.
        pc.timed_goto_state("Silence_after_Tone1", TONE_ON_DURATION)
    elif event == "exit":
        speaker.off() # Crucially, turn off the speaker when exiting this tone state.

def Silence_after_Tone1(event):
    """
    Handles the brief silence period after Tone 1 and before Tone 2.
    """
    if event == "entry":
        # The speaker is already off from Tone1_on's exit event.
        # Schedule transition to Tone 2 after the silence duration.
        pc.timed_goto_state("Tone2_on", SPEAKER_OFF_DURATION)
    elif event == "exit":
        # No specific action needed when exiting this state.
        pass

def Tone2_on(event):
    """
    Plays Tone 2 for a specified duration and then transitions to a silence state.
    """
    if event == "entry":
        # Changed from pc.printx to print for compatibility
        speaker.sine(TONE_FREQ_2) # Start playing Tone 2
        # Schedule transition to the silence state that follows Tone 2.
        pc.timed_goto_state("Silence_after_Tone2", TONE_ON_DURATION)
    elif event == "exit":
        speaker.off() # Turn off the speaker when exiting this tone state.

def Silence_after_Tone2(event):
    """
    Handles the brief silence period after Tone 2, before cycling back to Tone 1.
    """
    if event == "entry":
        # The speaker is already off from Tone2_on's exit event
        # Schedule transition back to Tone 1 after the silence duration, completing the cycle.
        pc.timed_goto_state("Tone1_on", SPEAKER_OFF_DURATION)
    elif event == "exit":
        # No specific action needed when exiting this state.
        pass

# --- Run End Behaviour ---

def run_end():
    """
    Function executed at the very end of the experiment run.
    Ensures the speaker is turned off cleanly.
    """
    speaker.off() # Crucially, ensure the speaker is turned off at the end of the run.
