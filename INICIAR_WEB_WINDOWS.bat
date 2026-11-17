@echo off
cd /d "%~dp0"
py -3 server_web.py --host 127.0.0.1 --web-port 8080
if errorlevel 1 python server_web.py --host 127.0.0.1 --web-port 8080
pause
