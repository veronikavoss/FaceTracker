@echo off
cd /d "%~dp0"
if exist "D:\Program Files\Python\pythonw.exe" (
    start "" "D:\Program Files\Python\pythonw.exe" "click_bar.py"
) else (
    start "" pythonw click_bar.py
)
