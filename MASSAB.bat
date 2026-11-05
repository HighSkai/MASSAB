@echo off
rem Starts MASSAB without leaving a terminal open.
cd /d "%~dp0"
start "" ".venv\Scripts\pythonw.exe" gui.py
