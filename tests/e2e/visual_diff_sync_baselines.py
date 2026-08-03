"""把 fliki.ai 参考截图同步为项目 visual_baselines.

--dry-run 默认: 只打印会拷哪些文件, 不写盘.
实际写入: 把 fliki_research/screenshots/fliki_*.png 拷到 tests/e2e/visual_baselines/project_<id>.png
(下一轮 visual_diff.py 跑时, 会拿当前项目 dist 截图跟这些 baseline 比).

警告: 这会让 baseline 与 fliki.ai 锁定, 后续如果项目视觉升级, 必须重新跑一次 sync
才能让 visual_diff 通过. 谨慎用.
"""
import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "fliki_research" / "screenshots"
DST = ROOT / "tests" / "e2e" / "visual_baselines"

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只列出会做什么, 不写盘")
    args = ap.parse_args()

    if not SRC.exists():
        print(f"missing {SRC} -- run visual_diff_fliki.py first", file=sys.stderr)
        return 1

    DST.mkdir(parents=True, exist_ok=True)
    fliki_files = sorted(SRC.glob("fliki_*.png"))
    if not fliki_files:
        print(f"no fliki_*.png in {SRC}", file=sys.stderr)
        return 1

    print(f"would copy {len(fliki_files)} fliki screenshots -> {DST}/project_<id>.png")
    for f in fliki_files:
        target = DST / f.name.replace("fliki_", "project_")
        print(f"  {f.name}  ->  {target.name}")
        if not args.dry_run:
            shutil.copy2(f, target)
    print(f"\n{'[dry-run] no changes written' if args.dry_run else '[done] baselines updated'}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
