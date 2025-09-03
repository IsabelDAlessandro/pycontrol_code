# audio_smoke_test.py
import pyControl.utility as pc
from hardware_definition import speaker

states = ['tone_on']
events = ['stop']
initial_state = 'tone_on'

def run_start():
    try:
        speaker.set_volume(0.9)
    except:
        try:
            speaker.set_volume(110)
        except:
            pass

def all_states(event):
    if event == 'stop':
        speaker.off()
        pc.stop_framework()

def tone_on(event):
    if event == 'entry':
        try:
            speaker.sine(1000)
        except:
            try:
                speaker.tone(1000)   # alternate method name on some builds
            except:
                pc.print("AUDIO_ERROR: no sine/tone method on Audio_board")
        pc.set_timer('stop', 20000)
