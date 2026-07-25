@echo off
rem === GPT-SoVITS 可选外部服务指引 (P6A) ===
rem Fliki 端不内置 GPT-SoVITS 模型; 本脚本只做"如何起服务 + Fliki 端怎么连"说明,
rem 不会自动下载任何东西, 不会写入任何 key.

echo === GPT-SoVITS P6A 联调 ===
echo 1. 在另一台机器 (或本机) 拉官方仓库并启 API:
echo    git clone https://github.com/RVC-Boss/GPT-SoVITS.git
echo    cd GPT-SoVITS
echo    python api_v2.py -a 0.0.0.0 -p 9880
echo.
echo 2. 浏览器打开 http://127.0.0.1:9880/docs 看到 API 文档即可.
echo.
echo 3. Fliki 端 .env 写入 (不要贴聊天, 自己 echo 到 .env):
echo    FLIKI_GPT_SOVITS_URL=http://127.0.0.1:9880
echo    FLIKI_GPT_SOVITS_REF_AUDIO=D:\refs\my_voice.wav
echo    FLIKI_GPT_SOVITS_REF_TEXT=参考文本, 用相同口音念
echo.
echo 4. 重启后端, 访问 http://127.0.0.1:5181/env-check 看 gpt_sovits.available.
echo.
echo 完整指引见 docs\GPT_SOVITS.md
