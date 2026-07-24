# Fliki 还原 P5D-7 短 Handoff（2026-07-24 收尾）

## 坐标
- 项目根：`D:\workspace\Fliki视频制作还原`
- 测试：84/84 绿（compileall 通过、Remotion tsc --noEmit 通过）
- 后端端口 8001（detached spawn + 等 40s startup diagnostic）

## P5D-7 改动落点
- `backend/workflow_pipeline.py`
  - 加 `_load_avatar_layout(connection)` helper：从 `provider_configs WHERE category='avatar' AND name='wav2lip_onnx'` 读 `config_json`；优先 `extra.avatar_layout`（PUT 把 extra 塞 nested），fallback 顶层 `avatar_layout`，非 dict 视 None
  - `execute_pipeline` 在 props dict 写 `"avatarLayout": global_avatar_layout`（music 节点后、render 节点前）
  - **bug 修**：`synthesize_scene_avatar` 第一行 `scene.get("avatar")` 在 sqlite3.Row 上 `AttributeError`，改 `scene["avatar"]` + KeyError 兜底
- `backend/tests/test_p5d7_avatar_layout.py`（新建 4 case）
  - 顶层字段、字段缺失、非 dict、坏 JSON
- `backend/tests/test_p5d7b_avatar_layout_extra.py`（新建 2 case）
  - extra 嵌套、缺 extra
- `Main.tsx`（上轮已改，未动）
  - `SceneProps.avatarLayout? / AvatarPosition / AvatarShape` 已 OK
  - `MainProps.aspectRatio / avatarLayout` 已 OK
  - `resolveLayout(scene, global)` 合并 + `avatarBoxStyle` + `subtitleReserve`

## 端到端真实渲染（run b11af87ec70244378d3d95c54003f997）
- avatar_clone (256×256 真 PNG，91 KB，zlib 压缩) → draft → scene PATCH `avatar:avatar:<uuid>` → PUT provider avatar_layout (top-left 240×240 circle `#00C8FF`) → confirm → from-draft → render
- MP4：`data/output/7a463d9274b04b4fbb27badd/7a463d9274b04b4fbb27badd.mp4`（1.27 MB / 1280×720 / H.264+AAC / 3.28s）
- props：`data/props/workflow-b11af87ec70244378d3d95c54003f997.json` 真的带 `"avatarLayout": {...}`

## 端到端脚本模板（python 不用 PS）
```python
import io, json, time, uuid, urllib.request, urllib.error
BASE = "http://127.0.0.1:8001"
def http(method, path, data=None, files=None):
    url = BASE + path
    if files:
        boundary = "----p5d7b" + uuid.uuid4().hex
        body = io.BytesIO()
        for k, v in (data or {}).items():
            body.write(f"--{boundary}\r\n".encode())
            body.write(f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode())
            body.write(str(v).encode("utf-8"))
            body.write(b"\r\n")
        for fk, (filename, content, ctype) in files.items():
            body.write(f"--{boundary}\r\n".encode())
            body.write(f'Content-Disposition: form-data; name="{fk}"; filename="{filename}"\r\n'.encode())
            body.write(f"Content-Type: {ctype}\r\n\r\n".encode())
            body.write(content)
            body.write(b"\r\n")
        body.write(f"--{boundary}--\r\n".encode())
        req = urllib.request.Request(url, data=body.getvalue(), method=method,
                                      headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    elif data is not None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=body, method=method, headers={"Content-Type": "application/json"})
    else:
        req = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read().decode("utf-8") or "null")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
# 步骤：POST /avatar-clones (multipart ref_face 真 PNG >= 256B) -> uuid
#       POST /workflow-drafts (source_script) -> draft_id, scene_id
#       PATCH /workflow-drafts/{draft_id}/scenes/{scene_id} (voice, avatar="avatar:<uuid>")
#       PUT /provider-configs/avatar/wav2lip_onnx (extra={"avatar_layout": {...}})
#       POST /workflow-drafts/{draft_id}/confirm
#       POST /workflow-runs/from-draft/{draft_id} -> run_id
#       轮询 GET /workflow-runs/{run_id} 直到 status=success/failed
#       ffprobe data/output/<job_id>/<job_id>.mp4 看 H.264/AAC
```

## 待跟进（差距 + 改进方向）
1. **scene 级 avatar_layout 覆盖**：`ScenePatchBody` 没加 `avatar_layout` 字段，目前所有 scene 共享 global 配置
2. **PUT 端点契约**：`avatar_layout` 嵌套在 `config_json.extra` 下不直观；可改 PUT 端点让 `avatar_layout` 直接落顶层（但会破现有 PUT 契约）
3. **后端 startup 阻塞 ~36s**：`run_full_diagnostic()` 联网探测卡 startup；可改后台任务跑
4. **Per-shape border radius 字段**：当前 shape→borderRadiusPx 硬编码映射
5. **假 PNG hang**：`b'\x89PNG\r\n\x1a\n' + b'\x00' * N` 让 wav2lip ffmpeg hang；生成测试 PNG 用 zlib 真压缩 + IHDR/IDAT/IEND

## 下一轮开场（30 秒内 resume）
```
读取 D:\workspace\规矩文档.txt、D:\workspace\踩坑日志.txt、D:\workspace\Fliki视频制作还原\HANDOFF.md
+ D:\workspace\Fliki视频制作还原\HANDOFF_P5D7_short.md（这个文件）
进入 D:\workspace\Fliki视频制作还原
跑 python -m unittest discover -s tests -q（应 84/84 绿）
然后从 P5D-7 改进点选一个：scene 级 avatar_layout 覆盖 / PUT 契约 / 后端 startup 异步化
```
