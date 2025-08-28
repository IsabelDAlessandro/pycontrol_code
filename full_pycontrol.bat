@echo off
call C:\Users\datta\anaconda3\Scripts\activate.bat pycontrol

REM --- CONFIG ---
set PYTHON=python
set BRIDGE=C:\Users\datta\Documents\code\pycontrol_code\tools\olf_bridge_tail.py
set ROOT=C:\Users\datta\Documents\2AFC\data\Isabel
set OLF_PORT=COM5
set LOGDIR=C:\Users\datta\Documents\code\pycontrol_code\tools\logs

if not exist "%LOGDIR%" mkdir "%LOGDIR%"

REM --- Start the Teensy bridge MINIMIZED ---
start "OLFBRIDGE" /min %PYTHON% "%BRIDGE%" --root "%ROOT%" --olf %OLF_PORT% 1>>"%LOGDIR%\bridge.out" 2>>"%LOGDIR%\bridge.err"

REM --- Your watcher (unchanged) ---
start "pycontrol-watcher" python "C:\Users\datta\Documents\code\pycontrol_code\tools\watcher_slack_min.py"

REM --- Launch pyControl GUI and wait here until it closes ---
python "C:\Users\datta\Documents\code\pycontrol_code\pyControl_GUI.pyw"

REM --- Clean up the bridge when GUI exits ---
taskkill /f /fi "WINDOWTITLE eq OLFBRIDGE"
