@echo off
setlocal
chcp 65001 > nul
echo === Fliki 本地 CI Runner ===
node "%~dp0ci.js"
exit /b %ERRORLEVEL%
