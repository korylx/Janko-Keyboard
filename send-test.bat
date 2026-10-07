@echo off
cd /d "%~dp0"
echo Sending CC11/CC12 test sweep to the loopMIDI port...
py -3 main.py --send-test
pause
