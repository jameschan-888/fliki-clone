# GPT-SoVITS 外部联调说明 (P6A)

本项目只做 **HTTP 客户端**——把合成请求发到你在另一台机器（同一台也行）跑起来的官方 GPT-SoVITS API 服务。
本目录不内置任何模型权重；不连接任何外部服务。

## 1. 起服务 (你做)

```powershell
# 拉官方仓库 (示例)
git clone https://github.com/RVC-Boss/GPT-SoVITS.git
cd GPT-SoVITS
# 准备参考音频 5-10 秒, 配参考文本; 启动 API (默认端口 9880)
python api_v2.py -a 0.0.0.0 -p 9880
```

启好后浏览器/curl 检查:

```bash
curl http://127.0.0.1:9880/docs   # 应返回 API 文档页面
```

## 2. Fliki 端连通 (一行命令)

```powershell
# 装上 key/value 写入 backend/.env (不要直接贴聊天)
Add-Content backend\.env "FLIKI_GPT_SOVITS_URL=http://127.0.0.1:9880"
Add-Content backend\.env "FLIKI_GPT_SOVITS_REF_AUDIO=D:\refs\my_voice.wav"
Add-Content backend\.env "FLIKI_GPT_SOVITS_REF_TEXT=这是参考文本, 请用相同口音念"
# 重启后端, 然后查 env-check
(Invoke-WebRequest http://127.0.0.1:5181/env-check).Content | ConvertFrom-Json | Select-Object -ExpandProperty gpt_sovits
```

期望: `available=True, http_status<500`。Fliki 合成请求固定发送到官方 API v2 的 `POST /tts`，字段使用 `ref_audio_path`。

## 3. 跑通合成

```powershell
# 直接走 Python 路径, 不必启动整个前端:
cd backend
python -c "from providers.tts.gpt_sovits import GPTSoVITSProvider; p=GPTSoVITSProvider(); print(p.synthesize_with_refs('你好, 这是 Fliki 试音.', r'out\tts.wav', r'D:\refs\my_voice.wav', '这是参考文本, 请用相同口音念', language='zh'))"
```

## 4. 失败回退

服务不在时, `check_gpt_sovits.available=False`, capability_groups 把 gpt_sovits 标为不可发布;
工作流默认走 edge_tts, 不影响主链路. 想强制只用 GPT-SoVITS, 走 PUT /provider-configs/tts 把 gpt_sovits 设为 default (需重启).

## 5. 注意事项

- 端口 9880 是默认; 改端口要同步改 `FLIKI_GPT_SOVITS_URL`.
- 合成上限 32MB (单次响应), 限 5s timeout 健康检查.
- 不在文档/聊天/截图里贴任何 API key; 走本地 .env.
- 本机默认 port=8001 / 5181 / 5180; Docker 用 8765.
