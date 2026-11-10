@echo off
rem Starts MASSAB. The first time, it sets up Python's packages in .venv first
rem (a few minutes), and it does that again whenever requirements.txt changes.
rem Once MASSAB has opened, MASSAB.lnk (with the M icon) does the same job.
setlocal
cd /d "%~dp0"
set "PY=.venv\Scripts\python.exe"
set "STAMP=.venv\massab-requirements.txt"

if exist "%PY%" goto check_packages
echo Setting up MASSAB for the first time. This takes a few minutes.
echo.
py -3.14 -m venv .venv 2>nul || py -3 -m venv .venv 2>nul || python -m venv .venv
if not exist "%PY%" (
    echo.
    echo Python isn't installed. Get Python 3.14 from https://www.python.org/downloads/
    echo and tick "Add python.exe to PATH" while installing, then run MASSAB.bat again.
    pause
    exit /b 1
)

:check_packages
fc /b requirements.txt "%STAMP%" >nul 2>&1 && goto start
echo Installing the Python packages MASSAB needs...
"%PY%" -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 (
    echo.
    echo Installing packages failed. Check your internet connection and run MASSAB.bat again.
    pause
    exit /b 1
)
copy /y requirements.txt "%STAMP%" >nul

:start
start "" ".venv\Scripts\pythonw.exe" app\gui.py
