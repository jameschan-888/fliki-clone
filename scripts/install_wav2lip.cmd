@echo off
rem === Wav2Lip-ONNX 模型本地化脚本 (Windows) ===
rem 默认放到 backend\data\models\wav2lip\wav2lip.onnx (与 Env-Check 默认路径一致).
rem 已存在且 >1MB 时跳过下载. 网络不通时给出离线提示.

setlocal
set "TARGET_DIR=%~1"
if "%TARGET_DIR%"=="" set "TARGET_DIR=%~dp0..\backend\data\models\wav2lip"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_wav2lip.ps1" -TargetDir "%TARGET_DIR:\=\%"
if errorlevel 1 (
  echo.
  echo [hint] 下载失败属正常; 拷本地 wav2lip.onnx 到 %TARGET_DIR%\wav2lip.onnx 即可使用.
)
endlocal
