@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    py -3.11 -m venv .venv
    if errorlevel 1 goto failed
)
if not exist ".venv\doctor-preview-ready" (
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 goto failed
    echo installed>".venv\doctor-preview-ready"
)
".venv\Scripts\python.exe" run.py
if errorlevel 1 goto failed
exit /b 0
:failed
echo Please use 64-bit Python 3.11 and check the error above.
pause
exit /b 1
