"""Remotion runner - 调用 npx remotion render 渲染视频"""
import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

WINDOWS_BROWSER_CANDIDATES = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
)


def resolve_browser_executable():
    configured = os.environ.get("REMOTION_BROWSER_EXECUTABLE")
    if configured:
        browser_path = Path(configured)
        if not browser_path.is_file():
            raise FileNotFoundError(
                f"REMOTION_BROWSER_EXECUTABLE does not exist: {browser_path}"
            )
        return str(browser_path)

    if platform.system() == "Windows":
        for candidate in WINDOWS_BROWSER_CANDIDATES:
            if Path(candidate).is_file():
                return candidate
    return None


def resolve_public_dir(props_path: Path):
    if not props_path.is_file():
        return None
    try:
        payload = json.loads(props_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    configured = payload.get("_publicDir")
    if not configured:
        return None
    public_dir = Path(configured)
    if not public_dir.is_dir():
        raise FileNotFoundError(f"Remotion public directory does not exist: {public_dir}")
    return str(public_dir)


def build_render_command(props_path: Path, output_path: Path):
    npx_cmd = "npx.cmd" if platform.system() == "Windows" else "npx"
    if not shutil.which(npx_cmd):
        raise RuntimeError(f"{npx_cmd} not found. Install Node.js 18+")

    command = [
        npx_cmd,
        "remotion",
        "render",
        "src/index.tsx",
        "Main",
        str(output_path),
        "--props",
        str(props_path),
        "--concurrency",
        "1",
    ]
    public_dir = resolve_public_dir(props_path)
    if public_dir:
        command.extend(["--public-dir", public_dir])
    browser_executable = resolve_browser_executable()
    if browser_executable:
        command.extend(["--browser-executable", browser_executable])
    return command


def render_progress_for_frame(rendered_frames: int, total_frames: int):
    if total_frames <= 0:
        return 0
    ratio = max(0, min(rendered_frames / total_frames, 1))
    return round(ratio * 87)

def parse_render_progress(output_line: str):
    match = re.search(r"Rendered\s+(\d+)/(\d+)", output_line)
    if not match:
        return None
    return render_progress_for_frame(int(match.group(1)), int(match.group(2)))

def resolve_ffmpeg_executable():
    configured = os.environ.get("FFMPEG_EXECUTABLE")
    if configured:
        ffmpeg_path = Path(configured)
        if not ffmpeg_path.is_file():
            raise FileNotFoundError(f"FFMPEG_EXECUTABLE does not exist: {ffmpeg_path}")
        return str(ffmpeg_path)

    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        raise RuntimeError(
            "ffmpeg not found. Install FFmpeg or set FFMPEG_EXECUTABLE"
        )
    return ffmpeg_path


def build_thumbnail_commands(
    video_path: Path,
    thumbnail_path: Path,
    preview_path: Path,
):
    ffmpeg = resolve_ffmpeg_executable()
    return [
        [
            ffmpeg,
            "-y",
            "-ss",
            "0.5",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(thumbnail_path),
        ],
        [
            ffmpeg,
            "-y",
            "-i",
            str(thumbnail_path),
            "-vf",
            "scale=320:-2",
            "-frames:v",
            "1",
            "-q:v",
            "3",
            str(preview_path),
        ],
    ]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--props", required=True, help="JSON file with Remotion props")
    parser.add_argument("--resolution", default="720p")
    parser.add_argument("--extension", default="mp4")
    parser.add_argument(
        "--remotion-project",
        default=str(Path(__file__).parent / "remotion-project"),
    )
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    remotion_dir = Path(args.remotion_project)
    output_dir = Path(args.output_dir) / args.job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{args.job_id}.{args.extension}"

    try:
        command = build_render_command(Path(args.props), output_path)
    except (FileNotFoundError, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(2)

    print(f"[remotion_runner] job={args.job_id}", flush=True)
    if "--browser-executable" in command:
        browser_index = command.index("--browser-executable")
        print(
            f"[remotion_runner] browser={command[browser_index + 1]}",
            flush=True,
        )

    print("[render-progress] 0", flush=True)
    process = subprocess.Popen(
        command,
        cwd=remotion_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    output_tail = []
    last_progress = -1
    if process.stdout is None:
        print("ERROR: Remotion stdout pipe was not created", file=sys.stderr)
        sys.exit(2)
    for output_line in process.stdout:
        output_tail.append(output_line)
        output_tail = output_tail[-200:]
        progress = parse_render_progress(output_line)
        if progress is not None and (
            progress == 87 or progress >= last_progress + 5
        ):
            print(f"[render-progress] {progress}", flush=True)
            last_progress = progress
    return_code = process.wait()
    if return_code != 0:
        print("FAILED:", "".join(output_tail)[-4000:], file=sys.stderr)
        sys.exit(return_code)
    print("[render-progress] 93", flush=True)

    thumbnail_path = output_dir / f"{args.job_id}_thumb.jpg"
    preview_path = output_dir / f"{args.job_id}_thumbPreview.jpg"
    try:
        thumbnail_commands = build_thumbnail_commands(
            output_path,
            thumbnail_path,
            preview_path,
        )
    except (FileNotFoundError, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(2)

    for thumbnail_command in thumbnail_commands:
        thumbnail_process = subprocess.run(
            thumbnail_command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        if thumbnail_process.returncode != 0:
            print(
                "THUMBNAIL FAILED:",
                thumbnail_process.stderr[-4000:],
                file=sys.stderr,
            )
            sys.exit(thumbnail_process.returncode)
        if thumbnail_command is thumbnail_commands[0]:
            print("[render-progress] 100", flush=True)

    size = output_path.stat().st_size if output_path.exists() else 0
    print(f"OK: {output_path} ({size} bytes)", flush=True)
    print(f"OK: {thumbnail_path} ({thumbnail_path.stat().st_size} bytes)", flush=True)
    print(f"OK: {preview_path} ({preview_path.stat().st_size} bytes)", flush=True)


if __name__ == "__main__":
    main()