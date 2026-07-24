import json, urllib.request, urllib.error
BASE = "http://127.0.0.1:8765"
def http(m, p, d=None):
    b = json.dumps(d, ensure_ascii=False).encode() if d is not None else None
    req = urllib.request.Request(BASE + p, data=b, method=m, headers={"Content-Type": "application/json"} if b else {})
    try:
        with urllib.request.urlopen(req, timeout=20) as r: return r.status, json.loads(r.read() or "null")
    except urllib.error.HTTPError as e: return e.code, e.read().decode("utf-8", "replace")
s, d = http("POST", "/workflow-drafts", {"source_script": "第一句。第二句。", "title": "p", "language": "zh-CN"})
print("DRAFT", s, d["id"], "scenes=", len(d["scenes"]))
sid = d["scenes"][0]["id"]
s, d2 = http("PATCH", f"/workflow-drafts/{d['id']}/scenes/{sid}", {"avatar_layout": {"position": "bottom-right", "size": 320}})
print("PATCH", s, "type=", type(d2).__name__, "body=", str(d2)[:300])
s, d3 = http("GET", f"/workflow-drafts/{d['id']}")
print("GET", s, "scenes0=", d3["scenes"][0])