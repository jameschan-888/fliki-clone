"""模板真实渲染端到端测试.

流程:
  1. 调后端 POST /workflow-drafts 创建草稿 (>=5 段脚本)
  2. 给每个 scene PATCH template_id + template_fields, 套上 5 套模板
  3. POST /workflow-drafts/{id}/confirm
  4. POST /workflow-runs/from-draft/{id} 创建真实 run (无 preview)
  5. 轮询 GET /workflow-runs/{id} 直到 success/failed
  6. 校验产物: MP4 存在, ffprobe 分辨率 1280x720, 时长 > 5s, size > 500KB
  7. 把 run_id/props 路径/MP4 路径/ffprobe 行写入 stdout, 失败时打印 message

依赖: 仅 Python 3.12 + ffmpeg (ffprobe). 不调任何付费 API.
"""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

BASE = os.environ.get("FLIKI_BASE", "http://127.0.0.1:5181")

# >= 5 句脚本, 对应 5 套模板
SCRIPT = (
    "第一条：欢迎来到我们的产品介绍视频，今天我们将为你展示本地化端到端模板渲染的最新成果，让每一个场景都能拥有电影级的视觉表现和细腻的转场效果，让创作者专注内容本身而无需操心复杂的剪辑工作。"
    "第二条：截至本月，我们的用户已经突破十万大关，这背后是无数个日夜打磨产品细节的工程师，是夜以继日编写文档的内容团队，也是社区里每一位给予反馈和支持的真实用户，你们共同构建了这个持续生长的创作平台，也共同见证了它从草根起步到如今覆盖全行业的全过程。"
    "第三条：第一步注册账号，访问主页右上角的注册按钮并填写你的邮箱与昵称，整个流程不超过三十秒；第二步完成认证，前往邮箱查收验证邮件并点击链接激活你的创作身份，激活后即可解锁全部模板与导出能力；第三步立即上手，回到主页粘贴你的第一段脚本并选择合适的模板与配音，让系统在数秒内为你生成高质量的草稿。"
    "第四条：正如爱因斯坦所说，想象力比知识更重要，知识是有限的，而想象力概括着世界上的一切，推动着进步，并且是知识进化的源泉，所以当我们面对一个全新领域时，比起查阅所有资料，更应该先问自己想创造什么样的作品，然后让工具帮助我们把这些想象变成真实的画面。"
    "第五条：立即扫码加入我们的官方社群，开启你的创作之旅，无论你是想制作企业宣传视频还是个人短视频频道，无论你是想做课程讲解还是节目导览，这里都有现成的模板等你来尝试，也有热心的社区成员随时准备帮你答疑解惑，更有官方团队定期举办直播分享创作技巧与最新功能。"
)

# 5 套模板对应的字段; 严格按 backend/data/templates.json 的 required 字段填写
TEMPLATE_PLAN = [
    {
        "template_id": "intro_simple",
        "template_fields": {
            "title": "Fliki 模板真实渲染",
            "subtitle": "P0-1 端到端验证",
            "logo_text": "E2E-TEST",
        },
    },
    {
        "template_id": "data_big_number",
        "template_fields": {
            "number": "100,000+",
            "unit": "用户",
            "description": "本地端到端闭环验证",
        },
    },
    {
        "template_id": "list_steps",
        "template_fields": {
            "step1_title": "写脚本",
            "step1_desc": "上传或粘贴你的文案",
            "step2_title": "套模板",
            "step2_desc": "为每段场景选定风格",
            "step3_title": "渲染发布",
            "step3_desc": "一键产出 MP4",
        },
    },
    {
        "template_id": "quote_card",
        "template_fields": {
            "quote": "想象力比知识更重要",
            "author": "爱因斯坦",
        },
    },
    {
        "template_id": "outro_cta",
        "template_fields": {
            "cta": "立即开始",
            "contact": "hello@fliki.local",
            "qr_placeholder": "扫码加入",
        },
    },
]

REQUIRED_FIELDS = {
    "intro_simple": ["title"],
    "data_big_number": ["number", "description"],
    "list_steps": ["step1_title", "step2_title", "step3_title"],
    "quote_card": ["quote", "author"],
    "outro_cta": ["cta"],
}


def http(method, path, data=None):
    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data is not None else None
    headers = {"Content-Type": "application/json"} if body is not None else {}
    req = urllib.request.Request(BASE + path, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8") or "null"
            return resp.status, json.loads(raw)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")


def ffprobe(path):
    out = subprocess.check_output(
        [
            "ffprobe", "-v", "error",
            "-print_format", "json",
            "-show_format", "-show_streams",
            path,
        ],
        stderr=subprocess.STDOUT,
        timeout=60,
    )
    meta = json.loads(out.decode("utf-8"))
    streams = meta.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), {})
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    fmt = meta.get("format", {})
    return {
        "width": int(video.get("width", 0) or 0),
        "height": int(video.get("height", 0) or 0),
        "duration": float(fmt.get("duration", 0.0) or 0.0),
        "size_bytes": int(fmt.get("size", 0) or 0),
        "has_audio": audio is not None,
    }


def main():
    print(f"=== Template E2E @ {BASE} ===")

    # 1) 创建草稿
    status, draft = http(
        "POST",
        "/workflow-drafts",
        {
            "source_script": SCRIPT,
            "title": "P0-1 模板端到端",
            "language": "zh-CN",
        },
    )
    assert status == 200, f"create draft failed: {draft}"
    draft_id = draft["id"]
    scenes = draft["scenes"]
    print(f"DRAFT {draft_id} scenes={len(scenes)}")
    assert len(scenes) >= len(TEMPLATE_PLAN), (
        f"scene count {len(scenes)} < template plan {len(TEMPLATE_PLAN)}"
    )

    # 2) 给每个 scene 套上模板 (取前 5 个 scene)
    for i, plan in enumerate(TEMPLATE_PLAN):
        scene_id = scenes[i]["id"]
        status, updated = http(
            "PATCH",
            f"/workflow-drafts/{draft_id}/scenes/{scene_id}",
            plan,
        )
        assert status == 200, f"PATCH scene {scene_id} -> {status}: {updated}"
        scene = updated["scenes"][i]
        assert scene["template_id"] == plan["template_id"], scene
        for f in REQUIRED_FIELDS[plan["template_id"]]:
            assert f in scene["template_fields"], (f, scene)
        print(f"  PATCH scene[{i}] template={scene['template_id']}")

    # 3) confirm
    status, confirmed = http("POST", f"/workflow-drafts/{draft_id}/confirm")
    assert status == 200, f"confirm failed: {confirmed}"
    assert confirmed["status"] == "confirmed", confirmed
    print("CONFIRMED")

    # 4) 创建真实 run (无 preview)
    status, run = http("POST", f"/workflow-runs/from-draft/{draft_id}")
    assert status == 200, f"create run failed: {run}"
    run_id = run["id"]
    print(f"RUN {run_id} status={run['status']}")

    # 5) poll
    deadline = time.time() + 1500
    final = None
    while time.time() < deadline:
        status, r = http("GET", f"/workflow-runs/{run_id}")
        assert status == 200, r
        progress = r.get("progress")
        nodes = " ".join(f"{n['node_type']}:{n['status']}" for n in r.get("nodes", []))
        print(f"  status={r['status']} progress={progress} {nodes}")
        if r["status"] in ("success", "failed"):
            final = r
            break
        time.sleep(5)
    assert final is not None, "run timeout (1500s)"
    assert final["status"] == "success", f"run failed: {final.get('message')!r}"

    # 6) 找到 MP4 路径 (render node 给出 jobId, MP4 在 backend/data/output/<jobId>/<jobId>.mp4)
    mp4_path = None
    render_job_id = None
    for n in final["nodes"]:
        if n["node_type"] == "render" and n.get("result"):
            rj = n["result"] if isinstance(n["result"], dict) else json.loads(n["result"])
            render_job_id = rj.get("jobId") or rj.get("output_path") or rj.get("mp4_path")
            break
    if render_job_id:
        candidate = os.path.join(os.getcwd(), "backend", "data", "output", render_job_id, f"{render_job_id}.mp4")
        if os.path.exists(candidate):
            mp4_path = candidate
        else:
            # fallback: scan the output directory
            output_root = os.path.join(os.getcwd(), "backend", "data", "output")
            if os.path.isdir(output_root):
                for entry in sorted(os.listdir(output_root), key=lambda x: os.path.getmtime(os.path.join(output_root, x)), reverse=True):
                    cand = os.path.join(output_root, entry, f"{entry}.mp4")
                    if os.path.exists(cand):
                        mp4_path = cand
                        break
    assert mp4_path and os.path.exists(mp4_path), f"MP4 not found: {mp4_path}"
    print(f"MP4 {mp4_path}")

    # 7) ffprobe 校验
    meta = ffprobe(mp4_path)
    print(f"FFPROBE {meta}")
    assert meta["width"] == 1280 and meta["height"] == 720, (
        f"unexpected resolution {meta['width']}x{meta['height']}"
    )
    assert meta["duration"] >= 5.0, f"duration too short: {meta['duration']}"
    assert meta["size_bytes"] >= 500_000, f"file too small: {meta['size_bytes']}"

    summary = {
        "draft_id": draft_id,
        "run_id": run_id,
        "mp4_path": mp4_path,
        "ffprobe": meta,
        "template_ids": [p["template_id"] for p in TEMPLATE_PLAN],
    }
    print("RESULT " + json.dumps(summary, ensure_ascii=False))
    return summary


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print(f"FAIL {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR {type(e).__name__}: {e}")
        sys.exit(2)
    print("PASS")

