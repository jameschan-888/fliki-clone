# Fliki 项目完成度与后续实施计划

更新时间：2026-07-25
项目根目录：`D:\workspace\Fliki视频制作还原`

## 结论

- 技术底座约 **91%**：后端、数据库、草稿状态机、Provider 编排、渲染、Auto-edit、环境自检和本地适配器已基本成形。
- 用户可跑通主链路约 **80%**：Script-to-video 与 Auto-edit 均已从输入走到真实 MP4，但前端 Avatar 选择、部署基线和真实外部 Provider 验证仍缺。
- 当前阶段适合继续做产品化收口，不适合重新抓站或大规模重写架构。

## 证据

| 验证项 | 结果 |
|---|---|
| Python 单元测试 | 宿主与 Docker 镜像内均 `152/152` 通过 |
| Python 编译 | `python -m compileall -q .` 通过 |
| 前端生产构建 | `npm.cmd run build` 通过 |
| Script-to-video | 草稿 → 编辑 → 确认 → Stock/TTS/Music → Remotion MP4 已闭环 |
| Auto-edit | 30 秒输入 → 转写/切分 → 编辑 → 确认 → 约 30.03 秒真实 MP4 |
| 渲染控制 | 进度、取消、硬超时、进程树回收已验证 |
| 数字人 | Wav2Lip-ONNX 适配器和静态回退已验证；模型本体尚未装入 |
| 声音 | Edge TTS Gallery 321 声音/142 locale；GPT-SoVITS HTTP 适配器已验证 |

## 模块评估

| 模块 | 完成度 | 当前判断 | 下一步 |
|---|---:|---|---|
| Phase 1-3 网站研究 | 100% | 已抓公开页、登录态页面、编辑器结构、API/Schema、渲染时间线 | 不再重复抓站 |
| FastAPI + SQLite | 95% | 主服务、初始化、19 张表、兼容增量逻辑已完成 | 后续只做拆分和运维 |
| Remotion + FFmpeg | 90% | 真实 MP4/JPG、进度、取消、超时、回收已完成 | 补 Docker 真验证 |
| P5A 场景草稿 | 100% | 草稿编辑、版本、排序、确认锁定和 UI 已完成 | 补 Avatar 字段/选择 |
| P5B 确认后流水线 | 95% | Stock → TTS → Music → Render 已真实跑通 | 修 Provider 密钥持久化 |
| P5C Auto-edit | 95% | 上传、ffprobe、Whisper、静音、草稿、确认、剪辑和重试已完成 | 增强异常提示和产品打磨 |
| Env-Check | 100% | 启动自检、Wav2Lip 明细和 Provider 发布能力矩阵已展示 | 后续仅维护 Provider 状态 |
| Voice Gallery | 90% | 321 声音/142 locale，试听链路已完成 | 与草稿选音交互再统一 |
| GPT-SoVITS | 75% | HTTP 适配器和 Mock 测试完成 | 外部服务联调，不嵌入主服务 |
| Wav2Lip-ONNX | 70% | 适配器、fallback、Env-Check 完成 | CPU 低分辨率真机验证 |
| 前端工作台 | 85% | drafts/autoedit/voices/avatar/env-check 页面可用 | 后续打磨 Provider 配置与发布提示 |
| 部署与版本管理 | 85% | Docker、Remotion 真渲染、数据卷、secrets 卷和 Git 基线已验证 | 补项目专用 `.venv` 与统一安装清单 |

## 当前缺口排序

### P0：影响产品闭环

1. **真实数字人模型尚未装入**：Avatar 已进入草稿编辑器，当前电脑缺模型时会稳定回退静态头像视频。
2. **README 与当前阶段有漂移**：README 仍有“待开发/下一步 P5B”等旧描述，应在产品化阶段统一。

### P1：影响交付

1. 没有项目专用 `.venv` 和一键安装/启动清单。
2. 外部 Pexels/Pixabay/Freesound 还需做一次网络、额度、授权和失败回退验收。

### P2：可选增强

1. Wav2Lip-ONNX 模型与依赖安装及低分辨率 CPU 验证。
2. GPT-SoVITS 外部 HTTP 服务联调。
3. 有 NVIDIA/CUDA 机器后再评估 SadTalker/MuseTalk。
4. 模板、历史版本、项目列表、完整 Composer 和更多媒体 Provider。

## 后续实施计划

### P5D-5：Avatar 前端接入

**目标**：用户在创建/编辑场景草稿时，可以选声音和 Avatar；确认后 Avatar 选择进入工作流。

实施项：

- 复用 Voice Gallery 的选择回传机制，补 Avatar 列表和预览。
- 草稿场景增加 `avatar` 字段，格式固定为 `avatar:<uuid>`。
- 确认快照保留 Avatar 字段；workflow pipeline 将其传到 Avatar 节点。
- Env-Check 页面显示模型是否存在、依赖是否完整、是否会走静态回退。
- 增加“未配置模型时仍能生成静态 Avatar MP4”的前端提示。

验收：

- 不确认草稿时，Avatar Provider 不被调用。
- 确认后可看到 Avatar 节点状态。
- 缺模型时任务不崩溃，明确显示 fallback。

### P5E：Provider 密钥持久化（已完成）

**目标**：用户可以在本机配置 Provider，重启后仍然有效，且前端永远看不到明文密钥。

已完成：

- `persist=true/false` 明确区分本地持久化与当前进程临时注入。
- 密钥写入独立 managed 段，不进入 SQLite，响应只返回掩码。
- 启动 hydrate、DELETE 清除、Docker secrets 卷与 0600 权限已验证。
- 宿主与 Docker 镜像内全量测试均为 `152/152`。

### P5D-7：部署与交接基线

**目标**：新电脑可以按清单启动，而不是依赖当前机器的隐式环境。

实施项：

- 固定 Python 版本并建立项目 `.venv`。
- 增加 Windows 启动/停止脚本和端口检查。
- 真运行 `docker compose up` 并记录结果；若 Docker 的 Remotion/Chrome 不稳定，保留本机系统 Chrome 路径为默认方案。
- 编写 `INSTALL.md`，只写已验证命令。
- 用户确认后创建首次 Git 基线提交；提交前清理或明确保留历史辅助脚本、旧日志和旧 DOCX。

### P5D-8：本地 AI 能力

**目标**：在不抬高当前电脑门槛的前提下增加可选数字人和克隆声音。

实施顺序：

1. Wav2Lip-ONNX：模型文件 → `librosa` 等依赖 → 低分辨率短视频 CPU 测试。
2. GPT-SoVITS：继续作为 HTTP 客户端；服务可在本机或局域网另一台机器运行。
3. SadTalker/MuseTalk：仅在有 NVIDIA/CUDA 机器或兼容远程 API 时进入候选。

## 推荐执行顺序

1. P5D-8：Wav2Lip CPU 真机验证和 GPT-SoVITS 外部联调。
2. 真实 Pexels/Pixabay/Freesound 网络、额度与失败回退验收。
3. 统一 README、安装清单和项目专用 `.venv`。
4. 最后再做模板、Composer 和更多 AI Provider。

## 不要做的事

- 不要重新抓 `app.fliki.ai`，除非出现明确的新功能缺口。
- 不要把截图作为结构或功能事实来源。
- 不要在当前 Intel/无 CUDA 机器上默认引入 SadTalker/MuseTalk 重模型。
- 不要在草稿确认之前调用付费或高算力 Provider。
- 不要把用户 API Key 写入文档、测试、前端 bundle 或 Git。
- 不要把 Mock 测试结果写成真实外部 API 已验证。

## 复用命令

```powershell
cd D:\workspace\Fliki视频制作还原\backend
python -m unittest discover -s tests -q
python -m compileall -q .

cd D:\workspace\Fliki视频制作还原\app
npm.cmd run build
```

## 文档状态

- 当前移交主文档：`D:\workspace\Fliki视频制作还原\HANDOFF.md`
- 当前状态计划：`D:\workspace\Fliki视频制作还原\PROJECT_STATUS_AND_PLAN.md`
- 规则：`D:\workspace\规矩文档.txt`
- 历史踩坑：`D:\workspace\踩坑日志.txt`
- 本次只更新上述两份 Markdown，没有修改源码、测试、抓取资料、API Key 或旧版 DOCX。
