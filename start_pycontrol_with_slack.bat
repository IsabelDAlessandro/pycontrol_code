@echo off
call C:\Users\datta\anaconda3\Scripts\activate.bat pycontrol
start "pycontrol-watcher" python "C:\Users\datta\Documents\code\pycontrol_code\tools\watcher_slack_min.py"
python "C:\Users\datta\Documents\code\pycontrol_code\pyControl_GUI.pyw"
