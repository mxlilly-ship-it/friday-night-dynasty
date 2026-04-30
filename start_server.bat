@echo off
cd /d "%~dp0"
where py >nul 2>&1 && py -3 run_game.py && exit /b 0
where python >nul 2>&1 && python run_game.py && exit /b 0
echo.
echo Python was not found. Install Python 3 from https://www.python.org/downloads/
echo Make sure "Add python.exe to PATH" is checked during setup.
echo.
pause
