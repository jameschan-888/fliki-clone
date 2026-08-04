"""模板真实渲染端到端测试 (rev36 P1.2: 加 auth).

流程:
  0. register + login 拿 JWT token
  1. 调后端 POST /workflow-drafts 创建草稿 (>=5 段脚本)
  2. 给每个 scene PATCH template_id + template_fields, 套上 5 套模板
  3. POST /workflow-drafts/{id}/confirm
  4. POST /workflow-runs/from-draft/{id} 创建真实 run (无 preview)
  5. 轮询 GET /workflow-runs/{id} 直到 success/failed
  6. 校验产物: MP4 存在, ffprobe 分辨率 1280x720, 时长 > 5s, size > 500KB
  7. 把 run_id/props 路径/MP4 路径/ffprobe 行写入 stdout, 失败时打印 message

依赖: 仅 Python 3.12 + ffmpeg (ffprobe). 不调任何付费 API.
env: FLIKI_DISABLE_RATE_LIMIT=1 跳过 register 端点限速 (CI 默认开)
"""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

BASE = os.environ.get("FLIKI_BASE", "http://127.0.0.1:5181").rstrip("/")

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


# 单 token 全局共享; register/login 调用前必须 reset 限速
TOKEN = None


def http(method, path, data=None, token=None):
    """通用 HTTP 调用. token 缺省用全局 TOKEN; 若 TOKEN=None 自动走匿名 (CI 应先 auth)."""
    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data is not None else None
    headers = {"Content-Type": "application/json"} if body is not None else {}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE + path, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8") or "null"
            return resp.status, json.loads(raw)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")


def auth():
    """register + login 拿 token. 每次重试确保 DB 干净 (CI fresh runner).
    返回: token 字符串.
    """
    # 用 UUID 后缀避免重复注册撞 409, 同时如果 FLIKI_DISABLE_RATE_LIMIT=1 也无所谓
    email = "e2e-" + uuid.uuid4().hex[:8] + "@fliki.local"
    pw = "long-enough-pw-test"
    # 先 reset 限速 (内部接口; 即使关限速也无副作用)
    try:
        urllib.request.urlopen(urllib.request.Request(BASE + "/auth/_internal/reset-rate-limits", method="POST"), timeout=5)
    except Exception:
        pass
    status, body = http("POST", "/auth/register", {"email": email, "password": pw, "role": "user"})
    if status not in (200, 201):
        # 409 = 已存在 (CI 重启复用 DB), 改走 login
        if status == 409:
            status, body = http("POST", "/auth/login", {"email": email, "password": pw})
        if status != 200:
            raise RuntimeError(f"auth failed: register/login returned {status} {body!r}")
    if isinstance(body, dict):
        token = body.get("token") or body.get("access_token")
    else:
        token = None
    if not token:
        # 重新 login 兜底
        status, body = http("POST", "/auth/login", {"email": email, "password": pw})
        if status != 200:
            raise RuntimeError(f"login fallback failed: {status} {body!r}")
        token = body.get("token") or body.get("access_token")
    if not token:
        raise RuntimeError(f"no token in auth response: {body!r}")
    return token


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
    global TOKEN
    print(f"=== Template E2E @ {BASE} ===")

    # 0) auth 拿 token
    TOKEN = auth()
    print(f"AUTH ok, token len={len(TOKEN)}")

    # 1) 创建草稿
    status, draft = http(
        "POST",
        "/workflow-drafts",
        {
            "source_script": SCRIPT,
            "title": "P0-1 模板端到端",
            "language": "zh-CN",
        },
        token=TOKEN,
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
            token=TOKEN,
        )
        assert status == 200, f"PATCH scene {scene_id} -> {status}: {updated}"
        scene = updated["scenes"][i]
        assert scene["template_id"] == plan["template_id"], scene
        for f in REQUIRED_FIELDS[plan["template_id"]]:
            assert f in scene["template_fields"], (f, scene)
        print(f"  PATCH scene[{i}] template={scene['template_id']}")

    # 3) confirm
    status, confirmed = http("POST", f"/workflow-drafts/{draft_id}/confirm", token=TOKEN)
    assert status == 200, f"confirm failed: {confirmed}"
    assert confirmed["status"] == "confirmed", confirmed
    print("CONFIRMED")

    # 4) 创建真实 run (无 preview)
    status, run = http("POST", f"/workflow-runs/from-draft/{draft_id}", token=TOKEN)
    assert status == 200, f"create run failed: {run}"
    run_id = run["id"]
    print(f"RUN {run_id} status={run['status']}")

    # 5) poll
    deadline = time.time() + 1500
    final = None
    while time.time() < deadline:
        status, r = http("GET", f"/workflow-runs/{run_id}", token=TOKEN)
        assert status == 200, r
        progress = r.get("progress")
        nodes = " ".join(f"{n['node_type']}:{n['status']}" for n in r.get("nodes", []))
        print(f"  poll [{int(time.time())}] status={r.get('status')} progress={progress} nodes={nodes}")
        st = r.get("status")
        if st in ("success", "failed"):
            final = r
            break
        time.sleep(8)
    assert final is not None and final.get("status") == "success", (
        f"run did not reach success in 25 min: {final}"
    )

    # 6) 校验产物
    run_dir = run.get("output_dir") or final.get("output_dir") or run.get("output_path") or final.get("output_path")
    mp4 = None
    if run_dir:
        candidate = os.path.join(run_dir, "final.mp4") if not str(run_dir).endswith(".mp4") else run_dir
        if os.path.exists(candidate):
            mp4 = candidate
        else:
            # 搜 outputs 下找 mp4
            for root, _, files in os.walk(run_dir):
                for fn in files:
                    if fn.endswith(".mp4"):
                        mp4 = os.path.join(root, fn)
                        break
                if mp4:
                    break
    assert mp4 is not None, f"no mp4 under {run_dir}"
    probe = ffprobe(mp4)
    print(f"MP4 {mp4} probe={probe}")
    assert probe["width"] == 1280 and probe["height"] == 720, probe
    assert probe["duration"] > 5, probe
    assert probe["size_bytes"] > 500 * 1024, probe
    print("PASS")


if __name__ == "__main__":
    main()
