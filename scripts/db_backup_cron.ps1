# rev24 阶段 D P1-C: Windows 计划任务包装 (cron 替代).
#
# 调用 db_backup.py backup, 保留 7 天最新 + 30 天 1 个, 删老的.
# 输出日志到 logs/db_backup_cron.log.
#
# 用法:
#   powershell -NoProfile -File scripts/db_backup_cron.ps1                      # 跑 backup + cleanup
#   powershell -NoProfile -File scripts/db_backup_cron.ps1 -Drill               # 跑 DR drill (周演练)
#   powershell -NoProfile -File scripts/db_backup_cron.ps1 -DryRun              # 看会做什么, 不真改
#
# 注册 Windows 任务计划 (admin):
#   $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument '-NoProfile -File "D:\workspace\Fliki视频制作还原\scripts\db_backup_cron.ps1"'
#   $trigger = New-ScheduledTaskTrigger -Daily -At "03:00"
#   Register-ScheduledTask -TaskName "FlikiDBBackup" -Action $action -Trigger $trigger -RunLevel Highest

param(
    [switch]$Drill,
    [switch]$DryRun,
    [int]$RetentionDays = 7,
    [int]$MonthlyRetentionDays = 30
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$RepoRoot = Split-Path -Parent $PSScriptRoot
# PS 5.1: -LiteralPath
$LogDir = Join-Path $RepoRoot "logs"
$LogFile = Join-Path $LogDir "db_backup_cron.log"
if (-not (Test-Path -LiteralPath $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir | Out-Null
}

function Write-Log {
    param([string]$Msg)
    $ts = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    $line = "[$ts] $Msg"
    Add-Content -LiteralPath $LogFile -Value $line -Encoding UTF8
    Write-Host $line
}

try {
    Write-Log "---- start db_backup_cron (Drill=$Drill DryRun=$DryRun) ----"
    $env:PYTHONIOENCODING = "utf-8"
    Push-Location $RepoRoot
    try {
        if ($Drill) {
            Write-Log "running DR drill..."
            $drillOutput = python scripts/db_backup_drill.py 2>&1
            Write-Log "drill output: $drillOutput"
            $drillJson = $drillOutput | ConvertFrom-Json -ErrorAction SilentlyContinue
            if ($drillJson -and $drillJson.drill_status -eq "passed") {
                Write-Log "DR drill PASSED (RTO=$($drillJson.rto_sec)s, verify_table_count=$($drillJson.verify_table_count))"
                exit 0
            } else {
                Write-Log "DR drill FAILED: $drillOutput"
                exit 2
            }
        }

        # 1) backup
        if ($DryRun) {
            Write-Log "[DRYRUN] would run: python scripts/db_backup.py backup"
        } else {
            Write-Log "running backup..."
            $backupOutput = python scripts/db_backup.py backup 2>&1
            Write-Log "backup output: $backupOutput"
        }

        # 2) cleanup old backups (保留 7 天所有 + 30 天每月 1 个)
        $BackupDir = Join-Path $RepoRoot "backend\data\backups"
        if (-not (Test-Path -LiteralPath $BackupDir)) { exit 0 }
        $cutoff = (Get-Date).AddDays(-$RetentionDays)
        $monthlyCutoff = (Get-Date).AddDays(-$MonthlyRetentionDays)
        $allBk = Get-ChildItem -LiteralPath $BackupDir -Filter "db-*.sqlite3" | Sort-Object LastWriteTime -Descending
        $removed = 0
        $kept = 0
        $idx = 0
        foreach ($f in $allBk) {
            $idx++
            if ($f.LastWriteTime -ge $cutoff) {
                $kept++
                continue
            }
            if ($f.LastWriteTime -ge $monthlyCutoff -and ($idx -le 5)) {
                # 30 天内 留 5 个分散
                $kept++
                continue
            }
            if ($DryRun) {
                Write-Log "[DRYRUN] would remove: $($f.Name) (mtime=$($f.LastWriteTime))"
            } else {
                Remove-Item -LiteralPath $f.FullName -Force
                $removed++
                Write-Log "removed old backup: $($f.Name)"
            }
        }
        Write-Log "cleanup: kept=$kept removed=$removed (cutoff=$($cutoff.ToString("yyyy-MM-dd")))"
    } finally {
        Pop-Location
    }
    Write-Log "---- done (exit 0) ----"
    exit 0
} catch {
    Write-Log "EXEC FAILED: $_"
    Write-Log "---- done (exit 2) ----"
    exit 2
}
