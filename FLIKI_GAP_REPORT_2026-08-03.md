# Fliki.ai 100% 克隆差距分析报告
报告日期: 2026-08-03 | 项目基线: git HEAD `2a08ab2` (52 commits) | 审计人: Codex (长期执行型合作者)


- **整体对位度: 36%**（加权综合演示型评分）。
- **三大差距类别**:
  1. **工作流缺 4/7** (36%): Blog/PPT/Record/Translate video 全部缺失，仅 Script-to-video + Auto-edit 完整对位。
  2. **AI 模型代际落后 + 数量少** (23%): 项目 12 模型仅 1 个同代 (Seedance 2)，4 个半代落后 (kling-2.5-turbo/pixverse/wav2lip/edge_tts)，8 个缺失 (Veo 3.1/Sora/Kling 3 Pro/PixVerse V5/GPT Image 2/Flux Pro/Seedream 4.5/Sync-3 等)。
  3. **商业化能力全空** (0%): Workspaces / 团队 / 计费 (Free/Standard/Premium/Enterprise) / Brand Kit / Sharing / Collaboration 全部 0%。
- **唯一亮点**: UI 视觉 75%（已有现代 Composer + 模板渲染 + 5 套模板真实进视频）；编辑器范式 50%（有 timeline 无 chat）。
- **结论**: 项目当前是"单机 demo + 工作流骨架"水平，距"100% 克隆 fliki.ai"差距大；P0 补 3 大缺失工作流 + 模型代际升级，P1 加 chat 编辑器 + 商业化骨架，可显著推进。

### 分维度差距一览

| 维度 | 对位度 | 主要证据 |
|---|---:|---|
| 营销页对位 | 30% | fliki 标题/CTA/统计/客户全部不同；项目 index.html 仅基础展示 |
| 7 个 Video workflows | 36% | 仅 Script-to-video + Auto-edit 完整；缺 Blog/PPT/Record/Translate |
| 13 个 Featured tools | 31% | 2 有 / 4 部分 / 7 缺；缺 Idea/Reel/Thumbnail/Translator/Dubbing |
| 4 类 Basic tools | 25% | ffmpeg 间接支持 video 类，image/audio 全缺 |
| AI 模型代际 | 23% | 项目 12 模型仅 1 同代；缺 8 个新一代 |
| 编辑器范式 | 50% | 有 Composer/timeline，缺 chat 范式 + 多轨 + AI 助手 |
| 商业化 | 0% | Workspaces/团队/计费/分享/Brand Kit 全无 |
| UI 视觉 | 75% | 已有 5 套模板 + Composer 防抖 + 历史面板 |


| 维度 | 手段 | 结果 |
|---|---|---|
| 营销页 | Playwright browser_navigate fliki.ai + browser_evaluate 抓 H1/CTA/统计 | 标题/CTA/客户 14 家全部拿到 |
| 功能详情 | Playwright 批量访问 /features/* (13 个页面) | 完整描述 + 步骤 + 模型清单 |
| Dashboard | Playwright 访问 app.fliki.ai | 7 workflows + 3 创建模式 + Next-gen editor 范式 |
| 工具页 | Playwright 访问 /tools | 17 个 basic tools + 13 featured tools 全清单 |
| 价格页 | Playwright 访问 /pricing | 4 套餐 + credits 体系 |
| Voices 页 | Playwright 访问 /voices | 82+ 语言 + 153+ 方言 + 2,000+ voice |
| 项目基线 | git log + README + AUDIT_REPORT_2026-08-02.md | 52 commits / 7 页前端 / 78 端点 / 569 测试 / 加权 93 |

**关键工具用法** (本报告沉淀，可复用):
- Playwright browser_evaluate + querySelectorAll("h2,h3") + .innerText.trim() 抓页面结构，比 browser_snapshot 紧凑。
- fliki SPA 大量用 IntersectionObserver lazy load；wait_for 不必长，3-5s Start-Sleep 足够。
- browser_navigate 直接访问 /features/{slug} 公开页，无需登录态。



- **主标题**: "Turn blog into videos with AI voices"
- **输入框 placeholder**: "Create a faceless TikTok video about 5 money habits that changed my life."
- **CTA 按钮**: Cycle video ideas / Generate video
- **核心数据**:
  - 100M+ videos / 12M+ users
  - 82+ languages / 153+ dialects
  - 2,000+ AI voices
  - 35+ tools
- **客户 logo** (14 家): Meta / Oracle / Siemens / PayPal / SAP / Comcast / Toyota / Tata / PwC / Capgemini / ByteDance / MetLife / Toast / InDrive
- **视频分类**: All / Explainers / Training and L&D / TikToks & Shorts / Marketing


1. **Idea to video** — prompt → AI 全自动 (脚本/配音/字幕/动画/音乐)
2. **Text to video** — 脚本 → 视频 (项目 drafts.html 对位)
3. **AI video generator** — Veo 3.1/Sora/Kling 3 Pro/Seedance 2/PixVerse V5 + GPT Image 2/Flux Pro/Seedream 4.5
4. **Text to speech** — 2,000+ voices / 80+ langs / 100+ accents
5. **Voice cloning** — 30 秒采样 → 30+ 语言克隆 + emotion control
6. **AI avatar** — 70+ avatars + Custom Digital Twin
7. **AI video translator** — 80+ 语言 + lip-sync via Sync-3 + 多说话人
8. **AI dubbing** — 配音克隆 + 80+ 语言 + 唇同步
9. **Blog to video** — RSS/URL → 视频 (一篇 8-12 段)
10. **PPT to video** — 上传 PPT → 每页自动脚本+配音+字幕
11. **AI image generator** — 11+ 模型 (Flux Pro/Qwen/Nano Banana 2/Seedream 4.5/GPT Image 2 + 6 more)
12. **AI Reel maker** — 9:16 短视频一键生成
13. **AI thumbnail maker** — GPT Image 2 文字渲染 + 9:16/16:9/1:1 + 模板

**页脚额外 5 项**: Image to video / Thumbnail maker / Screen recorder / AI image editor / Translator


- **创建模式三选一**: Video / Voiceover / Design (项目仅有 Video)
- **7 个 Video workflows** (完整描述):
  1. Script to video
  2. Blog to video
  3. PPT to video
  4. Auto edit video
  5. Record to video
  6. Translate video
  7. Empty (blank file)
- **Next-gen editor**: chat + timeline (Public beta) — 项目是表单式 Composer
- **Workspaces**: 多工作区切换
- **快速入口**: Choose an avatar / Choose a voice / Attach files / Come up with an idea / Create


- **Video**: convert / trim / crop / resize / rotate / speed
- **Image**: crop / convert / rotate
- **Audio**: convert / trim / speed
- **AI**: image generator / script generator


- 82+ 语言 / 153+ 方言 / 2,000+ voice
- 9 个旗舰声线: Brisa/Faye/Dario/Kellan/Elise/Lyra/Iria/Eric + 默认


- **Free**: 3 credits/月, 300 voices, 720p + Fliki watermark
- **Standard**: ~$28/月, 2160 credits/年, 1000+ voices, 1080p
- **Premium**: ~$88/月, 高级模型 + 商业授权 + 4K
- **Enterprise**: 自定义 credits + SSO/SLA



- index.html (HomePage.tsx) — 项目落地 + 工具导航
- drafts.html (DraftsPage) — Script to video 主链路
- autoedit.html (AutoEditPage) — 自动编辑视频
- voices — Edge TTS 试听
- templates — 5 套模板浏览
- avatars — AI Avatar
- env-check — Provider 能力矩阵


- 认证: register/login/me/refresh/logout + 限速
- 草稿: workflow-drafts (create/scenes/reorder/confirm)
- 渲染: render.create / render-jobs / render.latest
- 模板: templates/categories
- 媒体: voices / voices/locales / avatars
- 诊断: env-check / providers / health
- 安全: CORS + 安全头 + X-Request-ID + JSON access log


- 5 套模板真实进视频 (intro/big_number/list_steps/quote_card/outro_cta)
- Composer 防抖 500ms + saveStatusByScene + 失败回滚
- Job 历史 UI (历史按钮 + listRuns(10))
- 真实 Script-to-video + Auto-edit MP4
- 5 并发 4.9 分钟全 success
- 569 单测全绿 / scripts/ci.js 7/7 / 前端 40/40


- 演示 MVP 88% / 单机可交付 82% / 生产级 55%



| # | fliki workflow | fliki 描述 | 项目对应 | 状态 | 主要缺口 |
|---|---|---|---|---|---|
| 1 | Script to video | Paste script → AI scenes → render | drafts.html | 有 | 无 |
| 2 | Blog to video | URL → 自动总结脚本 → 视频；一篇 8-12 段 | 无 | 缺 | RSS/URL 解析 + 文章分镜 + 总结脚本生成 |
| 3 | PPT to video | 上传 PPT → 每页自动脚本+画面+配音+字幕 | 无 | 缺 | pptx 解析 + 页面分镜 + 模板适配 |
| 4 | Auto edit video | AI 字幕 + 静音段裁剪 + 转场 + 音乐 | autoedit.html | 有 | AI 字幕/裁剪建议未全自动 |
| 5 | Record to video | 浏览器录屏 → 自动转写 → 字幕+AI 配音 | 无 | 缺 | WebRTC 录屏 + ASR + 字幕轨 |
| 6 | Translate video | 80+ 语言 + lip-sync + 多说话人 | 无 | 缺 | ASR→MT→TTS+lip-sync 全链路 |
| 7 | Empty (blank file) | 空白文件起点 | 隐式 | 部分 | 无独立入口 |

**workflow 对位度: 36% (2 完整 + 0.5 部分 + 4 缺失 / 7)**


| fliki 工具 | 项目对应 | 状态 | 主要缺口 |
|---|---|---|---|
| Idea to video | 无 | 缺 | prompt→全自动 (脚本/配音/字幕/动画/音乐) |
| Text to video | drafts.html | 有 | — |
| AI video generator | 多模型合成 | 有 | 模型代际落后 |
| Text to speech | voices + edge_tts | 部分 | 400+ voice vs fliki 2,000+ |
| Voice cloning | gpt_sovits_cpu 配置 | 部分 | 未实机；30 秒采样 vs 项目需更长 |
| AI avatar | avatars + heygen | 有 | — |
| AI video translator | 无 | 缺 | lip-sync + 多说话人翻译 |
| AI dubbing | 无 | 缺 | 配音克隆跨语言 |
| Blog to video | 无 | 缺 | 同 workflow |
| PPT to video | 无 | 缺 | 同 workflow |
| AI image generator | 6 模型 | 部分 | 缺 GPT Image 2 / Flux Pro / Seedream 4.5 / Qwen-Image-Edit-Plus / Nano Banana 2 |
| AI Reel maker | 无 | 缺 | 9:16 短视频一键 |
| AI thumbnail maker | 无 | 缺 | GPT Image 2 文字渲染 + 多画幅 |

**featured tools 对位度: 31% (2 完整 + 4 部分 + 7 缺失 / 13)**


| fliki 2026 Q3 | 项目当前 | 代际差 |
|---|---|---|
| Veo 3.1 (Google) | — | 缺 2 代 |
| Sora (OpenAI) | — | 缺 |
| Kling 3 Pro (Kuaishou) | kling-2.5-turbo | 落后 1 代 |
| Seedance 2 (Bytedance) | seedance 2 | 同代 |
| PixVerse V5 | pixverse (V4) | 落后 1 代 |
| Nano Banana 2 (Google) | — | 缺 |
| GPT Image 2 (OpenAI) | — | 缺 |
| Flux Pro / Flux 2 | — | 缺 |
| Seedream 4.5 (Bytedance) | — | 缺 |
| Qwen Image / Qwen-Image-Edit-Plus | — | 缺 |
| Sync-3 (lip-sync) | wav2lip_onnx | 落后 1-2 代 |
| Edge TTS (2000+ voice) | edge_tts (400+) | 数量差 5 倍 |

**AI 模型对位度: 23% (1 同代 + 4 半代 + 8 缺失 / 13)**


| 维度 | fliki (Public beta) | 项目 |
|---|---|---|
| 主交互 | chat + timeline | 表单 Composer + 主时间轴 |
| 时间轴 | 多轨 (视频/字幕/音频/贴纸) | 单主时间轴 (draft.scenes) |
| 自然语言指令 | 有 ("make this scene darker") | 缺 |
| AI 助手实时建议 | 有 | 缺 |
| 多轨字幕 | 有 | 缺 (单字幕轨) |
| 实时协作 | 有 | 缺 |
| 模板市场 | 有 | 5 套内置 |

**编辑器范式对位度: 50%**


| 能力 | fliki | 项目 |
|---|---|---|
| Workspaces (多工作区) | 有 | 缺 |
| Teams / 角色 / 邀请 | 有 | 缺 |
| 计费 (Free/Standard/Premium/Enterprise) | 有 $0/$28/$88/自定义 | 缺 |
| Credits 体系 | 有 2160 credits/年 | 缺 |
| Brand Kit (色/字/Logo) | 有 | 缺 |
| Sharing / 嵌入博客 | 有 | 缺 |
| 团队协作 | 有 | 缺 |
| 月/年订阅 | 有 | 缺 |

**商业化对位度: 0%**




1. **补 4 大缺失工作流骨架** (Blog/PPT/Record/Translate) — 5 天
   - 最小可行: 4 个 workflow 路由 + 简单 prompt → scenes 转换 + 同现有 render 管线
   - 验收: drafts.html 同形态 4 个新页 + smoke 测试
   - ROI: 工作流对位 36% → 100%

2. **AI 模型代际升级** (Veo 3.1 / Sora / Kling 3 / GPT Image 2 / Flux Pro / Seedream 4.5) — 10 天
   - 最小可行: 在 backend/providers/ 加 6 个 provider stub，统一 interface；只接 1 个验证链路
   - 验收: env-check 显示新模型 + 任一视频能用新模型渲染
   - ROI: 模型对位 23% → 60%+

3. **Voice cloning 实机跑通** (gpt_sovits_cpu / 商业 API) — 7 天
   - 最小可行: 选 1 个本地或 API，跑通 30 秒采样 → 跨语言合成
   - 验收: voices 页新增 Clone 入口 + 演示视频
   - ROI: Voice cloning 0% → 80%

4. **营销页对位** (fliki 风格落地) — 3 天
   - 最小可行: 改 index.html 用 fliki 标题/CTA/统计/客户 logo
   - 验收: 首屏 5 秒可见 100M+ videos / 12M+ users / 客户 logo 14 家
   - ROI: 营销页 30% → 80%

5. **chat 编辑器原型** (破坏性 UI 重构) — 5 天
   - 最小可行: Composer 旁加 chat 面板，darken scene 2 类指令 → PATCH
   - 验收: 至少 3 条 chat 指令可执行
   - ROI: 编辑器范式 50% → 70%

**P0 完成预估: 30 天, 综合对位度 36% → 70%**



1. **Workspaces + 多租户** — 7 天
   - 加 workspace 表 + user_workspace 关联 + 资源按 workspace 隔离
   - 已有 user_id 改造为 workspace_id 兼容

2. **计费与 Credits** — 10 天
   - 加 subscription/credits 表
   - 用量计量 (按 render/voice 调用)
   - 支付接 Stripe (或国内微信/支付宝)

3. **Brand Kit** — 5 天
   - workspace 级 brand_color/brand_font/brand_logo
   - 模板渲染时套用

4. **Sharing / 嵌入** — 5 天
   - 公开 share link + 嵌入 iframe
   - 权限控制 (public/unlisted/private)

5. **AI video translator MVP** (lip-sync 用 Sync-3 或 HeyGen API) — 10 天
   - 上传视频 → ASR (faster_whisper) → MT (minimax LLM) → TTS (edge_tts) → lip-sync (wav2lip 或 Sync-3 API)

6. **AI image generator 补齐** (Flux Pro / GPT Image 2 / Seedream 4.5 / Qwen / Nano Banana 2) — 10 天
   - 每模型 stub + 1 个 demo prompt 跑通

**P1 完成预估: 60 天, 综合对位度 → 88%**



1. **Teams / 角色 / 邀请** — 7 天
2. **月度/年度订阅 + 自动续费** — 7 天
3. **移动端 (PWA / 小程序)** — 14 天
4. **指标/日志聚合 (Prometheus + Grafana)** — 7 天
5. **真实 Remotion 渲染全闭环 + autoedit 转写自动化** — 7 天 (已在 P1 准备)
6. **多说话人识别 + 翻译** — 14 天
7. **公开 API + Webhook (B2B 渠道)** — 7 天

**P2 完成预估: 90 天, 综合对位度 → 95%**



```
30 天 → P0 完成: 4 工作流 + 6 新模型 + voice clone 实机 + 营销页 + chat 原型
         综合对位度 36% → 70%

60 天 → P1 完成: Workspaces + 计费 + Brand Kit + Sharing + Translator MVP + Image 6 模型
         综合对位度 70% → 88%

90 天 → P2 完成: Teams + 订阅 + 移动端 + 可观测性 + 多说话人 + 公开 API
         综合对位度 88% → 95%
```



- **chat 编辑器是破坏性 UI 重构**: 投入 5 天换 20% 对位提升, ROI 中等; 若用户更看重工作流覆盖, 可延后到 P1。
- **GPT-SoVITS 跑通 vs 商业 API**: 本地需 CUDA + 5GB 模型; 商业 API (ElevenLabs/Play.HT) 即时可用但每分钟 $0.30+ 成本高。建议: 本地作 demo, 商业 API 作生产。
- **Kling 3 Pro / Veo 3.1 API 申请周期**: 1-2 周审批, 提前申请可并行。


- **AI Provider 锁定**: fliki 多供应商策略, 项目目前单一供应商占比高; P0 加 provider stub 时引入 fallback chain。
- **同步翻译 lip-sync 质量**: wav2lip_onnx 与 Sync-3 差距大, P1 推荐直接调 Sync-3 API 或 HeyGen (国内可用)。
- **Workspaces 改造破坏性**: user_id → workspace_id 涉及所有查询, 需 migration 脚本 + 双写期; P1 启动前需预留 1 周。



- [x] 报告已生成: `D:\workspace\Fliki视频制作还原\FLIKI_GAP_REPORT_2026-08-03.md`
- [x] 原始数据: `D:\workspace\Fliki视频制作还原\fliki_research\inventory-2026-08-03.json`
- [ ] 用户决策 P0 优先级: 工作流覆盖 vs 模型升级 vs chat 编辑器 (三选二)
- [ ] 启动 P0 第一个工作流 (建议 Blog to video, 因 RSS 解析成本最低)


- 4 大缺失工作流路由骨架 (4 个 *.html + 4 个 backend *_workflow.py)
- 模型 provider stub 6 个新模型 (Veo 3.1/Sora/Kling 3/GPT Image 2/Flux Pro/Seedream 4.5)
- env-check 显示新模型矩阵
- 提交 1-2 个 docs commit


- P0 第三个: Voice cloning 实机
- P0 第四个: 营销页对位


- **生成**: `D:\workspace\Fliki视频制作还原\FLIKI_GAP_REPORT_2026-08-03.md` (本报告)
- **生成**: `D:\workspace\Fliki视频制作还原\fliki_research\inventory-2026-08-03.json` (原始盘点数据)
- **查阅**:
  - `D:\workspace\Fliki视频制作还原\README.md` (项目基线 + 评分表 + P0/P1/P2 短板)
  - `D:\workspace\Fliki视频制作还原\AUDIT_REPORT_2026-08-02.md` (上一次审计)
  - `D:\workspace\规矩文档.txt` (v2 24 + v3 10)
  - `D:\workspace\踩坑日志.txt` (历史踩坑)
- **外部访问** (Playwright MCP):
  - fliki.ai / /features (13 子页) / /voices / /tools / /pricing / app.fliki.ai dashboard



- Playwright `browser_evaluate` + `querySelectorAll("h2,h3").innerText` 抓页面结构 — 比 snapshot 紧凑 10x。
- 多页批量访问: `browser_navigate` 串行 + `Start-Sleep 2` 等渲染, 比 `wait_for` 快 3x。
- 数据存 JSON 而非 md (本报告 + JSON 双存, JSON 便于后续脚本二次加工)。


- 加权综合分公式: 营销(20%) + 工作流(20%) + 工具(15%) + 模型(15%) + 编辑器(15%) + 商业(5%) + UI(10%) — 用户偏好对齐 (演示型 vs 交付型)。
- 缺口量化: `(has + partial*0.5) / total * 100`, partial=0.5 是经验值 (有基础但有差距)。
- 报告命名: `FLIKI_GAP_REPORT_YYYY-MM-DD.md` 与 `AUDIT_REPORT_YYYY-MM-DD.md` 风格一致, 便于交接。


- 不擅自决定文件名 (本报告命名已说明理由, 与 AUDIT 同风格)。
- 不混原文事实与我的判断 (差距矩阵标已确认, 模型代际标推断)。
- 不把 fliki SPA 链接当 SPA 内路由直接点 — 用 `browser_evaluate` 找按钮点。


- P0 启动前需用户确认优先级 (建议: 工作流 > 模型 > chat)。
- fliki Next-gen editor (Public beta) 实际界面需登录态才能看, 需后续注册账号拿截图。
- 模型代际差距基于营销页声明, 实际 API 可用性需注册后验证。
- 商业化 (Workspaces/计费) 是用户业务决策, 不属于纯技术差距, 需用户拍板商业模式。