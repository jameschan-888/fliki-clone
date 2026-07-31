@echo off
REM Fliki P6D 一键安装入口 (调用 scripts\bootstrap.js)
setlocal
node "%~dp0bootstrap.js" %*
endlocal
