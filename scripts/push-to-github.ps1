# P1-3: 一键 push 当前 master 到 GitHub + 触发 CI
# 用法 (任选其一):
#   1) 环境变量: $env:GITHUB_REPO="user/repo"; $env:GITHUB_TOKEN="ghp_xxx"; powershell scripts/push-to-github.ps1
#   2) 参数:       powershell scripts/push-to-github.ps1 -Repo "user/repo" -Token "ghp_xxx"
#
# 幂等: 已存在 remote 'origin' 时跳过 add, 只 set-url 刷新凭据; 没有 token 时直接打印说明.

param(
  [string]$Repo = $env:GITHUB_REPO,
  [string]$Token = $env:GITHUB_TOKEN
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not $Repo) {
  Write-Host "PUSH_TO_GITHUB: missing repo" -ForegroundColor Yellow
  Write-Host "  用法 1: $env:GITHUB_REPO='your-name/fliki-clone'; $env:GITHUB_TOKEN='ghp_xxx'; powershell scripts/push-to-github.ps1"
  Write-Host "  用法 2: powershell scripts/push-to-github.ps1 -Repo 'your-name/fliki-clone' -Token 'ghp_xxx'"
  Write-Host ""
  Write-Host "前置: 在 GitHub 创建一个空 repo (不要 README/.gitignore), 拿到 PAT (Settings -> Developer settings -> Personal access tokens, 勾 'repo')." -ForegroundColor Cyan
  exit 2
}

if ($Token) {
  $auth = $Token
} else {
  Write-Host "PUSH_TO_GITHUB: no token, will try 'git push' (only works if credential helper already configured)" -ForegroundColor Yellow
}

$existing = git remote get-url origin 2>$null
if ($LASTEXITCODE -eq 0) {
  Write-Host "[1/3] origin already set: $existing"
} else {
  if ($Token) {
    $url = "https://${auth}@github.com/${Repo}.git"
  } else {
    $url = "https://github.com/${Repo}.git"
  }
  Write-Host "[1/3] git remote add origin $url"
  git remote add origin $url
}

if ($Token) {
  $url = "https://${auth}@github.com/${Repo}.git"
  git remote set-url origin $url
}

Write-Host "[2/3] git push -u origin master (会触发 .github/workflows/ci.yml)"
if ($Token) {
  git push -u origin master
} else {
  git push -u origin master
}

if ($LASTEXITCODE -ne 0) {
  Write-Host "[FAIL] push 失败, 检查 GH_REPO 是否正确, token 是否过期, repo 是否已建好" -ForegroundColor Red
  exit 1
}

Write-Host "[3/3] OK. 打开 https://github.com/$Repo/actions 看 CI 跑 (~6 分钟, 全 9 phase)." -ForegroundColor Green
