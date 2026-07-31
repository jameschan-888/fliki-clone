@echo off
REM Fliki P6D 前端 dev (端口 5180)
setlocal
cd /d "%~dp0..\app"
npm.cmd run dev -- --host 127.0.0.1 --port 5180
endlocal
