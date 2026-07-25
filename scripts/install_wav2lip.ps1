param([string]$TargetDir)
$ErrorActionPreference = "Stop"
if (-not $TargetDir) { $TargetDir = "D:\workspace\Fliki视频制作还原\backend\data\models\wav2lip" }
New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
$dest = Join-Path $TargetDir "wav2lip.onnx"
if (Test-Path $dest) {
  $size = (Get-Item $dest).Length
  if ($size -gt 1MB) {
    Write-Host ("[exists] " + $dest + " (" + $size + " bytes); skip download")
    exit 0
  }
  Remove-Item $dest -Force
}
$urls = @(
  "https://huggingface.co/bluefoxcreation/Wav2lip-Onnx/resolve/main/wav2lip.onnx",
  "https://github.com/facefusion/facefusion-assets/releases/download/models/wav2lip_gan.onnx",
  "https://www.modelscope.cn/models/cjc1887415157/facefusion-assets/resolve/master/wav2lip_gan.onnx"
)
foreach ($u in $urls) {
  try {
    Write-Host ("[download] " + $u)
    Invoke-WebRequest -Uri $u -OutFile $dest -UseBasicParsing -TimeoutSec 180 -MaximumRedirection 5
    $size = (Get-Item $dest).Length
    if ($size -gt 1MB) {
      Write-Host ("[ok] " + $dest + " (" + $size + " bytes)")
      exit 0
    }
    Remove-Item $dest -Force
  } catch {
    Write-Host ("[fail] " + $_.Exception.Message)
  }
}
Write-Host ""
Write-Host "[hint] 三方源在本机网络不可达. 把本地 wav2lip.onnx 拷到:"
Write-Host ("       " + $dest)
Write-Host "       即可触发 Env-Check 标记 ok=True; 否则继续走 static_avatar 静态回退."
exit 2
