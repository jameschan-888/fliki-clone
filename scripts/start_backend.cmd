@echo off
REM Fliki P6D 后端启动 (本机端口 5181, 避开 8001 Hyper-V 排除区)
setlocal
node "%~dp0start_backend.js" %*
endlocal
