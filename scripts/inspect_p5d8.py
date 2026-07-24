import json, urllib.request, sys, os, subprocess
rid = sys.argv[1]
with urllib.request.urlopen(f"http://127.0.0.1:8765/workflow-runs/{rid}", timeout=10) as r:
    run = json.loads(r.read())
props_path = None
for n in run["nodes"]:
    if n["node_type"] == "render":
        rj = n.get("result")
        if isinstance(rj, str):
            try: rj = json.loads(rj)
            except: rj = {}
        if isinstance(rj, dict):
            props_path = rj.get("props_path")
            mp4_name = rj.get("media_generated_id", {}).get("file") if rj.get("media_generated_id") else None
            job_id = rj.get("jobId")
print("PROPS_PATH:", props_path)
if props_path and os.path.exists(props_path):
    props = json.load(open(props_path, "r", encoding="utf-8"))
    print(f"SCENES={len(props['scenes'])}")
    for i, s in enumerate(props["scenes"]):
        print(f"  scene{i}: id={s['id'][:8]} dur={s['durationInSeconds']}s videoSrc={bool(s.get('videoSrc'))} audioSrc={bool(s.get('audioSrc'))} avatar={s.get('avatarMode') or 'none'} layout={s.get('avatarLayout')}")
    print(f"TOP_AVATARLAYOUT={props.get('avatarLayout')}")
    print(f"RESOLUTION={props.get('_resolution', 'n/a')}")

# Find MP4
job_dir = os.path.join("D:/workspace/Fliki视频制作还原/backend/data/output")
if os.path.isdir(job_dir):
    for d in os.listdir(job_dir):
        full = os.path.join(job_dir, d)
        if not os.path.isdir(full): continue
        if rid[:8] in d:
            for f in os.listdir(full):
                if f.endswith(".mp4"):
                    p = os.path.join(full, f)
                    sz = os.path.getsize(p)
                    print(f"MP4: {p} size={sz} bytes")
                    try:
                        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,codec_name", "-of", "json", p], capture_output=True, text=True, timeout=10)
                        print("FFPROBE:", r.stdout.strip())
                    except Exception as e:
                        print("ffprobe_err:", e)