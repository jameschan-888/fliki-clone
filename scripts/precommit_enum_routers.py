"""pre-commit wrapper: 跑 enum_routers.py --check-routes + --update-handover + 自动 stage HANDOVER_NEXT.md.

rev40 R22: 与 R18 enum-routers-check hook 互补, 本脚本:
  1. check-routes: 任何 router 文件未在 main.py import 时 exit 1 (commit 拒绝)
  2. update-handover: 自动重生成 HANDOVER_NEXT.md 顶部 router 表 section
  3. git add HANDOVER_NEXT.md (如果变化) 让同 commit 一起带走

与 R18 不同: R18 只跑 check (拒绝 fail), R22 跑 check + update + stage (强制同步).

需要 git 在 PATH 中 (pre-commit language: system 默认满足).
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HANDOVER = ROOT / "HANDOVER_NEXT.md"


def run(cmd: list[str]) -> int:
    print(f"\n>>> {' '.join(cmd)}", flush=True)
    return subprocess.call(cmd, cwd=ROOT)


def main() -> int:
    rc = run([sys.executable, "scripts/enum_routers.py", "--check-routes"])
    if rc != 0:
        return rc

    rc = run([sys.executable, "scripts/enum_routers.py", "--update-handover"])
    if rc == 2:
        print("[precommit] HANDOVER_NEXT.md 不存在, 跳过 update-handover 步骤", flush=True)
        return 0
    if rc != 0:
        return rc

    if not HANDOVER.exists():
        print("[precommit] HANDOVER_NEXT.md 仍不存在, 跳过 stage", flush=True)
        return 0

    rc = run(["git", "add", "HANDOVER_NEXT.md"])
    if rc != 0:
        return rc

    diff_rc = subprocess.call(
        ["git", "diff", "--cached", "--name-only", "--", "HANDOVER_NEXT.md"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
    )
    if diff_rc != 0:
        print("[precommit] HANDOVER_NEXT.md 已 stage, 请确认 commit message 涵盖", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
