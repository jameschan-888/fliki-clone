# 灾备 Runbook (rev24 阶段 D P1-C)

项目: Fliki 视频制作还原  ·  更新时间: 2026-07-29  ·  维护: 后端运维

## 1. 目标

保证核心 DB (`backend/data/app.db`) 可在任意时刻被备份 + 恢复 + 演练. 量化目标:

| 指标 | 目标 | 实测 (rev24 P1-C) |
|---|---|---|
| RTO (Recovery Time Objective) | < 5 min | **< 1s** (drill 实测) |
| RPO (Recovery Point Objective) | < 24h | = cron 间隔 (建议 24h) |
| Backup 完整性 | 100% 表可读 | 29 表 / 96 users / 196 jobs / 85 runs |
| 演练频率 | 每周 1 次 (drill) + 每月 1 次 (smoke) | cron -Drill 周一 03:00 |

## 2. 备份策略

### 2.1 备份方式

- **冷备份**: SQLite `shutil.copy2` (后端单进程无并发写, 安全)
- 备份目录: `backend/data/backups/db-YYYYMMDD-HHMMSS.sqlite3`
- 备份大小: ~100MB (随 usage 增长)
- 备份耗时: < 1s (本地 SSD)

### 2.2 保留策略

`scripts/db_backup_cron.ps1` 默认保留:

- **7 天内**: 全部保留 (每日 backup)
- **30 天内**: 保留 5 个分散 (月末备份)
- **> 30 天**: 自动删除

手动调整: `db_backup_cron.ps1 -RetentionDays 14 -MonthlyRetentionDays 60`

### 2.3 定时任务 (Windows)

```powershell
# 注册任务计划 (管理员):
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument '-NoProfile -ExecutionPolicy Bypass -File "D:\workspace\Fliki视频制作还原\scripts\db_backup_cron.ps1"'
$trigger = New-ScheduledTaskTrigger -Daily -At "03:00"
Register-ScheduledTask -TaskName "FlikiDBBackup" -Action $action -Trigger $trigger -RunLevel Highest

# 注册周演练 (周一 03:30):
$trigger_drill = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At "03:30"
$action_drill = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument '-NoProfile -ExecutionPolicy Bypass -File "D:\workspace\Fliki视频制作还原\scripts\db_backup_cron.ps1" -Drill'
Register-ScheduledTask -TaskName "FlikiDBDrill" -Action $action_drill -Trigger $trigger_drill -RunLevel Highest
```

## 3. 灾备演练 (DR Drill)

### 3.1 演练脚本

`scripts/db_backup_drill.py` 完整闭环:

1. **backup** - 复制 DB 到 `backups/drill-db-<ts>.sqlite3`
2. **verify** - sqlite3 打开 + 列所有表 (必须 29 张)
3. **restore_to_temp** - 复制到 `backups/drill-tmp/restore-test.sqlite3` (不动生产 DB)
4. **smoke_test** - 验证 4 关键表 (users / render_jobs / workflow_runs / workflow_drafts) + 行数
5. **cleanup** - 删除临时文件 + 默认删 drill backup

### 3.2 触发演练

```powershell
# 完整 drill (一次性):
python scripts/db_backup_drill.py

# 通过 cron 脚本 (推荐, 写到日志):
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/db_backup_cron.ps1 -Drill

# 演练后保留 backup (调试用):
python scripts/db_backup_drill.py --keep-backup

# 不删 temp restore (调试用):
python scripts/db_backup_drill.py --no-cleanup
```

### 3.3 演练成功标志

JSON `drill_status` = `"passed"` + 5 步 `ok` 都 true. 实测:

```json
{
  "drill_status": "passed",
  "rto_sec": 0.246,
  "verify_table_count": 29,
  "restore_test_passed": true,
  "steps": [...]
}
```

### 3.5 深度 smoke (P0#3)

drill 只验 '备份能打开', 不动生产 DB. smoke 在沙箱里真删真恢复, 验证恢复链路真能跑通.

**scripts/db_backup_smoke.py** 7 步:

1. **copy_to_sandbox** - 复制生产 DB 到 backend/data/smoke/sandbox.sqlite3, 记录 sha256
2. **backup** - 备份沙箱 DB
3. **delete_sandbox** - 真删沙箱 DB
4. **restore_from_backup** - 从 backup 复制回沙箱
5. **hash_check** - sha256 与原值对比
6. **row_count_check** - 4 关键表 (users / render_jobs / workflow_runs / workflow_drafts) 行数一致
7. **cleanup** - 删沙箱 + 临时 backup

**用法**:
\\powershell
python scripts/db_backup_smoke.py
# 退出 0 = passed, 2 = failed
\
**沙箱路径**: \ackend/data/smoke/\ (不污染生产 + 不污染 backups/)

**CI 集成**: scripts/ci.js 阶段 10, 与 backend tests 同 group 1 并行跑.

**最近一次 smoke (2026-08-06)**:
- 沙箱 sha256: 3f6a5a48375b4f6e8c6c12ebdf2e1ffcd171635ff7a0536e7a793dc524a37267
- 4 表行数: users=2066 / render_jobs=799 / workflow_runs=85 / workflow_drafts=184
- RTO: 0.55s
- 全 7 步 OK

### 3.4 演练失败排查

| 失败步骤 | 可能原因 | 排查 |
|---|---|---|
| backup | DB 锁 / 权限 | 杀残留 uvicorn + 检查 Lock |
| verify | 备份损坏 | 重新 backup + sha256 比对 |
| restore_to_temp | 磁盘满 | df / D 盘剩余 |
| smoke_test | 缺表 / schema 不匹配 | DB schema.sql check |
| cleanup | 权限 | PowerShell admin |

## 4. 真实恢复流程

### 4.1 触发条件

需要立即恢复 DB 时:

- DB 文件损坏 (e.g. `sqlite3.DatabaseError: file is not a database`)
- 误操作 drop table / delete 全部数据
- 磁盘损坏 (DB 文件被截断)
- D 盘爆满导致 DB 写入失败

### 4.2 恢复步骤 (3 步, < 5min)

```powershell
# 1. 停后端
$proc = (Get-NetTCPConnection -LocalPort 5181 -State Listen -ErrorAction SilentlyContinue).OwningProcess
if ($proc) { Stop-Process -Id $proc -Force }
Start-Sleep -Seconds 2

# 2. 选 backup
python scripts/db_backup.py list
# 输出示例:
# {
#   "backups": [
#     { "name": "db-20260729-030000.sqlite3", "size_bytes": 103264256, "mtime": 1785235200 },
#     ...
#   ]
# }

# 3. 恢复 (当前 DB 自动备份到 backups/auto/)
python scripts/db_backup.py restore --from backend/data/backups/db-20260729-030000.sqlite3 --confirm

# 4. 重启后端
cmd /c "start /B node D:\workspace\Fliki视频制作还原\scripts\start_backend.js"
Start-Sleep -Seconds 4
curl http://127.0.0.1:5181/health

# 5. smoke test
curl http://127.0.0.1:5181/metrics  # 应 200 + 含 4 类 user 维度
curl -X POST http://127.0.0.1:5181/auth/login -d '{"email":"existing_user","password":"..."}'  # 应 200
```

### 4.3 验证清单

| 检查 | 命令 | 预期 |
|---|---|---|
| 后端 200 | curl /health | `{"status":"ok"}` |
| metrics 含 user 维度 | curl /metrics | 含 4 metric series |
| 登录可用 | curl /auth/login | 返回 token |
| 用户数据 | sqlite3 open | 96 users / 196 render_jobs |
| DR drill 复跑 | python scripts/db_backup_drill.py | drill_status=passed |

## 5. 监控与告警

### 5.1 备份告警 (P1-B 已实现)

通过 `/api/alerts/eval` 触发:

- `backup_age_cron` (warning, planned P1-C 之后增量): 最新 backup > 24h
- `drill_age` (warning, planned): 上次成功 DR drill > 7 天

当前生效规则: render_queue_full / queue_depth_high / error_rate_high / user_high_failure

### 5.2 备份健康检查

cron 脚本日志: `logs/db_backup_cron.log`

```powershell
# 看最近 30 天备份列表 + 健康状态
Get-ChildItem backend/data/backups -Filter "db-*.sqlite3" |
    Sort-Object LastWriteTime -Descending |
    Select-Object Name, Length, LastWriteTime |
    Format-Table -AutoSize
```

## 6. 故障预案

### 6.1 备份目录本身损坏

1. 临时禁用 cron
2. 重建 `backend/data/backups/` 目录
3. 立刻跑一次 `python scripts/db_backup.py backup`
4. 优先做 DR drill 验证

### 6.2 DB 锁导致 backup 失败

1. `Get-CimInstance Win32_Process | Where-Object {$_.CommandLine -match "uvicorn|remotion"} | Stop-Process -Force`
2. `Remove-Item backend/data/app.db-journal, backend/data/app.db-wal, backend/data/app.db-shm -ErrorAction SilentlyContinue`
3. 重试 backup

### 6.3 后端启动后 DB 仍异常

用历史 24h 内 backup 恢复 (RPO 24h):

```powershell
python scripts/db_backup.py restore --from backend/data/backups/db-<最近一次成功 backup> --confirm
```

## 7. 参考

- 备份脚本: `scripts/db_backup.py` (rev15, 子命令 backup/restore/list/verify)
- 演练脚本: `scripts/db_backup_drill.py` (rev24 阶段 D P1-C, 8.8KB)
- Windows 包装: `scripts/db_backup_cron.ps1` (rev24 阶段 D P1-C, 4.2KB)
- 演练测试: `backend/tests/test_p1c_backup_drill.py` (rev24 阶段 D P1-C, 8 case)   
- Smoke 自动化: `scripts/db_backup_smoke.py` (P0#3, 7 步沙箱真删真恢复 + hash)
- 关联: `docs/MONITORING.md` (P1-B 告警), `HANDOVER_NEXT.md` (P1 周)
