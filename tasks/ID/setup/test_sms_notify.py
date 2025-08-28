import pyControl.utility as pc

# Define a trivial state machine
states = ['wait']
events = ['session_timer']
initial_state = 'wait'

# Run length: 20 seconds
pc.v.session_duration = 20 * pc.second

def run_start():
    # Set timer that will trigger the "session_timer" event in 20s
    pc.set_timer('session_timer', pc.v.session_duration)
    pc.print("Test task started – will finish in 20s.")

def run_end():
    # Print sentinel that watcher_email_sms.py looks for
    pc.print("SESSION_DONE")

def wait(event):
    if event == 'session_timer':
        # End the session cleanly
        pc.stop_framework()
