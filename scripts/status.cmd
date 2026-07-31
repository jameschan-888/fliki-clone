@echo off
REM Fliki P6D 状态检查 (端口 + 进程 + /health)
setlocal
set PIDFILE=%~dp0..\.run\backend.pid

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "function CheckPort($port, $name) {" ^
  "  $pid_ = (Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique);" ^
  "  if ($pid_) { Write-Host ('[' + $name + '] 端口 ' + $port + ' LISTEN pid=' + ($pid_ -join ',')) }" ^
  "  else { Write-Host ('[' + $name + '] 端口 ' + $port + ' 空闲') };" ^
  "};" ^
  "CheckPort 5181 '后端';" ^
  "CheckPort 5180 '前端';" ^
  "if (Test-Path '%PIDFILE%') {" ^
  "  $procId = Get-Content '%PIDFILE%' -ErrorAction SilentlyContinue;" ^
  "  if ($procId -and (Get-Process -Id $procId -ErrorAction SilentlyContinue)) { Write-Host ('[pidfile] .run\backend.pid = ' + $procId + ' 进程存活') }" ^
  "  else { Write-Host ('[pidfile] .run\backend.pid = ' + $procId + ' 进程已死, 请清理') }" ^
  "} else { Write-Host '[pidfile] 无 .run\backend.pid' };" ^
  "try {" ^
  "  $r = Invoke-WebRequest -Uri 'http://127.0.0.1:5181/health' -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop;" ^
  "  $c = ($r.Content -replace '\s+',' ').Trim();" ^
  "  if ($c.Length -gt 80) { $c = $c.Substring(0,80) + '...' };" ^
  "  Write-Host ('[/health] HTTP ' + $r.StatusCode + ' ' + $c)" ^
  "} catch { Write-Host '[/health] 后端未响应' }"
endlocal
