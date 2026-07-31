# rev24 阶段 D D1-2: Windows 计划任务注册 (需 admin 权限)
# 用法: 右键 -> 以管理员身份运行 PowerShell -> 跑这个脚本
# 或: Start-Process powershell -Verb runAs -ArgumentList "-NoProfile -File D:\workspace\Fliki视频制作还原\scripts\register_cron.ps1"
#
# 注册 2 个任务:
#   FlikiDBBackup      每日 03:00 跑 backup + cleanup
#   FlikiDBDrill       每周日 04:00 跑 DR drill

$ErrorActionPreference = "Stop"
$RepoRoot = "D:\workspace\Fliki视频制作还原"
$LogDir = Join-Path $RepoRoot "logs"
if (-not (Test-Path -LiteralPath $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }

# 1) FlikiDBBackup 每日 03:00
$act1 = New-ScheduledTaskAction -Execute "powershell.exe" -Argument ('-NoProfile -File "' + (Join-Path $RepoRoot "scripts\db_backup_cron.ps1") + '"')
$trg1 = New-ScheduledTaskTrigger -Daily -At "03:00"
Register-ScheduledTask -TaskName "FlikiDBBackup" -Action $act1 -Trigger $trg1 -RunLevel Highest -Description "Fliki 日备 + 清理 (>7d)" -Force | Out-Null
Write-Host "[OK] FlikiDBBackup 已注册 (每日 03:00)"

# 2) FlikiDBDrill 每周日 04:00 (用 -Weekly)
$act2 = New-ScheduledTaskAction -Execute "powershell.exe" -Argument ('-NoProfile -File "' + (Join-Path $RepoRoot "scripts\db_backup_cron.ps1") + '" -Drill')
$trg2 = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At "04:00"
Register-ScheduledTask -TaskName "FlikiDBDrill" -Action $act2 -Trigger $trg2 -RunLevel Highest -Description "Fliki DR drill (周演练)" -Force | Out-Null
Write-Host "[OK] FlikiDBDrill 已注册 (每周日 04:00)"

# 验证
Write-Host ""
Write-Host "=== 当前 Fliki 计划任务 ==="
Get-ScheduledTask -TaskName "FlikiDB*" | Format-Table TaskName,State,@{N='NextRun';E={$_.NextRunTime}} -AutoSize
