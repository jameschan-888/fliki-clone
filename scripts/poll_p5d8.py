import json, urllib.request, urllib.error, time, sys
rid = sys.argv[1]
for i in range(60):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:8765/workflow-runs/{rid}", timeout=10) as r:
            d = json.loads(r.read())
    except Exception as e:
        print(f"poll_err: {e}"); time.sleep(3); continue
    s = d["status"]; p = d["progress"]; nodes = " ".join(f"{n['node_type']}:{n['status']}" for n in d["nodes"])
    print(f"  {s} {p}% {nodes}")
    if s in ("success", "failed"): print("FINAL", s, d.get("message")); break
    time.sleep(3)