@echo off
call C:\Users\datta\anaconda3\Scripts\activate.bat pycontrol

set PYTHON=python
set ROOT=C:\Users\datta\Documents\2AFC\data\Isabel\training_box_right
set WATCHER=C:\Users\datta\Documents\code\pycontrol_code\tools\watcher_slack_min_recursive.py

start "pycontrol-watcher" %PYTHON% "%WATCHER%" --base "%ROOT%"
%PYTHON% "C:\Users\datta\Documents\code\pycontrol_code\pyControl_GUI.pyw"
