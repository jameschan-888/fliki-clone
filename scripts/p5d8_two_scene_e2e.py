"""P5D-8 端到端：2 scene + preview=1 + ffmpeg 校验"""
import io, json, time, uuid, urllib.request, urllib.error
import subprocess, sys, threading

BASE = "http://127.0.0.1:8765"

def http(method, path, data=None, ctype="application/json"):
    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data is not None else None
    req = urllib.request.Request(BASE + path, data=body, method=method,
        headers={"Content-Type": ctype} if body else {})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read().decode("utf-8") or "null")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")

# 1) Draft + scene with avatar_layout
src = "第一条：脚本会自动拆出场景，方便你编辑。第二条：多场景可以拼接成完整视频。"
status, draft = http("POST", "/workflow-drafts", {"source_script": src, "title": "P5D-8 双场景", "language": "zh-CN"})
assert status == 200, draft
print(f"DRAFT {draft['id']} scenes={len(draft['scenes'])}")
did, sids = draft["id"], [s["id"] for s in draft["scenes"]]

# 2) 第一个 scene 加 avatar_layout 覆盖
s0 = draft["scenes"][0]
patch = {"avatar_layout": {"position": "bottom-right", "size": 320, "shape": "rounded"}}
status, draft2 = http("PATCH", f"/workflow-drafts/{did}/scenes/{s0['id']}", patch)
assert status == 200 and draft2["scenes"][0]["avatar_layout"]["position"] == "bottom-right"
print("SCENE_LAYOUT_OK")

# 3) Confirm
status, _ = http("POST", f"/workflow-drafts/{did}/confirm")
assert status == 200, _
print("CONFIRMED")

# 4) Run with preview=1
status, run = http("POST", f"/workflow-runs/from-draft/{did}?preview=1")
assert status == 200, run
rid = run["id"]
print(f"RUN {rid} status={run['status']}")

# 5) Poll
deadline = time.time() + 240
while time.time() < deadline:
    status, r = http("GET", f"/workflow-runs/{rid}")
    s = r["status"]
    p = r["progress"]
    nodes = " ".join(f"{n['node_type']}:{n['status']}" for n in r["nodes"])
    print(f"  {s} {p}% {nodes}")
    if s in ("success", "failed"): break
    time.sleep(4)
final = r
print("FINAL", final["status"], final.get("message"))

# 6) Read props
import os
props_path = None
for n in final["nodes"]:
    if n["node_type"] == "render" and n.get("result"):
        rj = n["result"] if isinstance(n["result"], dict) else json.loads(n["result"])
        props_path = rj.get("props_path")
print("PROPS_PATH", props_path)
if props_path and os.path.exists(props_path):
    with open(props_path, "r", encoding="utf-8") as f:
        props = json.load(f)
    print(f"SCENES_IN_PROPS={len(props['scenes'])}")
    for i, s in enumerate(props["scenes"]):
        print(f"  scene{i}: id={s['id']} dur={s['durationInSeconds']} layout={s.get('avatarLayout')}")
    print(f"AVATARLAYOUT_TOP={props.get('avatarLayout')}")

# 7) Read MP4
mp4 = None
for n in final["nodes"]:
    if n["node_type"] == "render" and n.get("result"):
        rj = n["result"] if isinstance(n["result"], dict) else json.loads(n["result"])
        # media info is in render_jobs; try direct file
mp4_glob = os.path.join(os.path.dirname(props_path or "."), "..", "outputs", f"{rid}.mp4")
mp4_glob = os.path.abspath(mp4_glob)
print("MP4_TRY", mp4_glob, os.path.exists(mp4_glob))