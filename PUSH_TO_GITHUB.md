# 推送到 GitHub 触发 CI

## 一次性准备 (2 分钟)

1. **建空 repo** — GitHub 网页 -> New repository -> Name 任取 (例如 `fliki-clone`) -> 不要勾 README/.gitignore/license -> Create
2. **拿 PAT** — GitHub 右上头像 -> Settings -> Developer settings (左下) -> Personal access tokens -> Tokens (classic) -> Generate new token
   - Scopes 勾 `repo` (完整仓库访问)
   - 复制 token (形如 `ghp_xxxxxxxxxxxxxxxxxxxx`)

## 一键 push

PowerShell 在项目根目录:

```powershell
$env:GITHUB_REPO = "your-name/fliki-clone"
$env:GITHUB_TOKEN = "ghp_xxxxxxxxxxxxxxxxxxxx"
powershell scripts/push-to-github.ps1
```

或者纯命令行:

```powershell
powershell scripts/push-to-github.ps1 -Repo "your-name/fliki-clone" -Token "ghp_xxxxxxxxxxxxxxxxxxxx"
```

## push 后

打开 `https://github.com/your-name/fliki-clone/actions` 看 CI:

- 9 个 phase 顺序跑 (~6 分钟沙箱拆跑 / ~12 分钟 GitHub Actions 默认):
  1. 路由挂载检查
  2. 后端单元测试 (全量)
  3. API 合约测试
  4. Provider 联调测试 (联网, allowFail)
  5. Remotion TS 编译
  6. 前端生产构建
  7. 前端 vitest
  8. 模板预览 smoke (强 gate)
  9. **前端视觉回归 (visual_diff)** ← P1-3 新增, threshold 0.1%

任意 phase 红 = push 阻断 / merge 阻断.

## 不想用 GH Actions 也能跑

本地全 9 phase:

```powershell
node scripts/ci.js
```

只跑 visual_diff:

```powershell
cd app && npm run visual-diff
```

更新 visual_diff 基线 (refactor 后用):

```powershell
cd app && npm run visual-diff:update
```
