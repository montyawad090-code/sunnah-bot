@echo off
REM ===== Sunnah Companion bot launcher (Windows) =====
cd /d "%~dp0"
echo Starting Sunnah Companion bot...
echo (Keep this window open. Close it to stop reminders.)
echo.
where py >nul 2>nul && (py -m pip install -q requests & py sunnah_bot.py) || (python -m pip install -q requests & python sunnah_bot.py)
pause
