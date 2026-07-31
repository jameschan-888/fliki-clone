@echo off
REM Fliki P6D 后端停止 (按 .run\backend.pid, 兜底端口 5181 反查)
setlocal
set PIDFILE=%~dp0..\.run\backend.pid

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$pidFile = '%PIDFILE%';" ^
  "$killed = $false;" ^
  "if (Test-Path $pidFile) {" ^
  "  $procId = Get-Content $pidFile -ErrorAction SilentlyContinue;" ^
  "  if ($procId -and (Get-Process -Id $procId -ErrorAction SilentlyContinue)) {" ^
  "    Write-Host ('Stop-Process pid=' + $procId);" ^
  "    Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue;" ^
  "    $killed = $true;" ^
  "  };" ^
  "  Remove-Item $pidFile -ErrorAction SilentlyContinue;" ^
  "};" ^
  "$portPid = Get-NetTCPConnection -State Listen -LocalPort 5181 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique;" ^
  "if ($portPid) {" ^
  "  foreach ($p in $portPid) {" ^
  "    Write-Host ('Stop-Process port-pid=' + $p);" ^
  "    Stop-Process -Id $p -Force -ErrorAction SilentlyContinue;" ^
  "    $killed = $true;" ^
  "  };" ^
  "};" ^
  "if ($killed) { Write-Host 'OK: 后端已停止' } else { Write-Host 'NOOP: 后端未在运行' }"
endlocal
