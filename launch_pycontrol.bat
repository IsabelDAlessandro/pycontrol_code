@echo off
REM ==== EDIT: Your conda base path and env name ====
set "CONDA_BASE=c:\users\tdt\anaconda3"
set "CONDA_ENV=pycontrol"

REM ==== EDIT: Your repo/tools paths ====
set "REPO=C:\Users\TDT\Documents\pycontrol_code"
set "BRIDGE=%REPO%\tools\olf_bridge_tail.py"
set "WATCHER=%REPO%\tools\watcher_slack_min_recursive.py"

REM ==== EDIT: Data root and Teensy COM port ====
REM IMPORTANT: set this to the pyControl *Data* folder that actually receives .tsv files
set "DATA_ROOT=C:\Users\TDT\Documents\pycontrol_code\data"
set "TEENSY_COM=COM10"
set "BAUD=115200"

REM ---- Activate conda env ----
call "%CONDA_BASE%\Scripts\activate.bat" "%CONDA_ENV%"
if errorlevel 1 (
  echo [ERROR] Could not activate conda env "%CONDA_ENV%".
  pause
  exit /b 1
)

REM ---- CD to repo (so relative imports work) ----
pushd "%REPO%"

REM ---- Ensure logs dir exists (optional) ----
if not exist "%REPO%\logs" mkdir "%REPO%\logs"

REM ---- Start bridge in its own window (UNBUFFERED, visible, no redirection) ----
REM Use -u for low latency printing; give the window a clear title.
start "OLFBRIDGE" cmd /c python -u "%BRIDGE%" --root "%DATA_ROOT%" --olf %TEENSY_COM% --baud %BAUD%

REM ---- OPTIONAL: also tee bridge output to a log while keeping the live window ----
REM Comment the 'start OLFBRIDGE' above and use this block instead if you want logs too.
REM start "OLFBRIDGE" powershell -NoLogo -NoProfile -Command ^
REM   "$p = Start-Process -PassThru python -ArgumentList '-u','""%BRIDGE%""','--root','""%DATA_ROOT%""','--olf','%TEENSY_COM%','--baud','%BAUD%';" ^
REM   "Start-Transcript -Path '""%REPO%\logs\olf_bridge.log""' -Append;" ^
REM   "Wait-Process -Id $p.Id; Stop-Transcript"

REM ---- (Optional) Start watcher in its own window ----
if exist "%WATCHER%" (
  start "pycontrol-watcher" cmd /c python "%WATCHER%" 1^>^>"%REPO%\logs\watcher.log" 2^>^&1
)

REM ---- Launch pyControl GUI in the foreground window ----
if exist "%REPO%\pyControl_GUI.pyw" (
  python "%REPO%\pyControl_GUI.pyw"
) else (
  echo [ERROR] Could not find pyControl_GUI.pyw at "%REPO%".
  pause
)

REM ---- Clean up the bridge when GUI exits (optional) ----
REM taskkill /f /fi "WINDOWTITLE eq OLFBRIDGE"

REM ---- Return to original directory ----
popd
