# Remotion 模板设计规范 (Motion Doctrine)

更新时间: 2026-07-27 (P0-6 落)
适用版本: rev12+ (P5D-8 真实 Wav2Lip-ONNX + 本地完整闭环)
目标读者: 写 Remotion 模板的开发者 / AI
单一来源: 本文件就是设计规范, 不再分散到各 .tsx 注释

---

## 0. 三句话总纲

1. 模板设计 以“镜头动作 + 浮层 + 字幕 + 转场”四轴组成, 不引入“特效 / 动画 / 颜色调色”等 Fliki 原生不提供的概念.
2. 任何浮层、字幕、转场都不能遮住安全区 (marginPx 默认 80, aspect 16:9 下水平上下各 80 px).
3. 不引入外部 CDN / 字体 / 动画库; 颜色 / 间距 / 圆角一律从 styles/app.css design tokens 读, 不在模板里 hardcode.

---

## 1. 镜头动作 (CameraMotion)

枚举 (Remotion Main.tsx 已实现):

| 动作 | 参数 | 适用场景 | 限制 |
|---|---|---|---|
| none | scale=1 | 静态背景 / 照片 / 交谈 | 默认, 不动 |
| zoom-in | scale 1.0 → 1.08 | 交谈 / 接近主体 | 范围不超 8%, 避免脸部裁切 |
| zoom-out | scale 1.08 → 1.0 | 结束 / 代入下一场 | 同上 |
| pan-left | translateX 0 → -32 | 横向产品展示 | 偏移不超 5% 宽度 |
| pan-right | translateX 0 → +32 | 同上, 反向 | 同上 |
| pan-up | translateY 0 → -32 | 高空 / 天空镜头 | 偏移不超 5% 高度 |
| pan-down | translateY 0 → +32 | 同上, 反向 | 同上 |

硬约束:
- 一个 scene 不超过 1 种镜头动作, 多种会让观感乱.
- zoom 与 pan 不同时使用 (组合会出现抖动).
- 动作起始帧不超过 scene 首帧的 10%, 避免刚进入就被抢镜.

---

## 2. Avatar 浮层规则

枚举 (Main.tsx 已实现):

- position: top-left / top-right / bottom-left / bottom-right / top-center / bottom-center / center
- shape: circle (半径 = max/2) / rounded (默认 16px) / square (0)
- size: 宽 × 高 px, 默认 320 × 240
- marginPx: 默认 80, 不低于 32 (低于安全区)
- border: 默认 rgba(255,255,255,0.92) 3px

安全区约束:
- 16:9 (1280×720) 有效内容区: 左右各 80px, 上下各 80px
- 9:16 (720×1280) 有效内容区: 左右各 64px, 上下各 96px (上下预留更多字幕)
- 1:1 (720×720) 有效内容区: 左右各 80px, 上下各 80px

Avatar 与字幕避让:
- bottom-* 位置默认 向上让出 subtitleReserve (72 px), 避免遮住字幕
- center 位置必须同时缩小 avatar 尺寸 (≤ 240×180), 避免遮住中间背景主体

---

## 3. 字幕双轨字段

scene 表需提供两个字段 (P0-4 落地):

- subtitle_display: 用于屏幕展示的文本 (可包含繁体 / 多行 / emoji)
- subtitle_spoken: 用于 TTS 合成的口语 (不含 <umm> / <chuckle> 等 SSML 标签)

处理流程:
1. 用户输入 script 后, LLM 生成 subtitle_display + subtitle_spoken 两个列.
2. subtitle_spoken 走 TTS (边缘 TTS / MiniMax TTS / GPT-SoVITS)
3. subtitle_display 走 Remotion 字幕处理代码, 默认单行不超过 20 个字, 超出自动换行.
4. 两者不一致不会冲突, 允许 subtitle_display 比 subtitle_spoken 多一些表情 / 过渡.

---

## 4. 转场规则

枚举 (Pixelle VideoTransitionMode 倒入, P1-7 未接入):

| 转场 | 参数 | 适用场景 | 限制 |
|---|---|---|---|
| none | durationMs=0 | 默认 | 不产生转场成本 |
| fade | durationMs=300 | 默认推荐, 字幕 + 背景渐入渐出 | 不超 600 ms |
| cut | durationMs=0 | 交谈号 / 产品跳切 | 不低于 16:9 中间 80 px |
| slide-left | durationMs=400 | 走马灯片 | 仅 9:16, 横向 |
| slide-up | durationMs=400 | 同上, 纵向 | 仅 9:16, 纵向 |

硬约束:
- 一个项目不超过 2 种转场类型, 避免得意乭忘型.
- slide 与 fade 不同时使用, 避免运动冲突.
- 转场纪要低于 600 ms, 超过会让观感拖没.

---

## 5. 不要做的事 (红线)

- 不要在 Remotion 代码里 import Google Fonts / jsdelivr / unpkg, 会被浏览器拦截.
- 不要用 Tailwind 或第三方动画库 (GSAP / Lottie), 会打突 tsx 类型推断.
- 不要在 scene 里写“特效” (fire / smoke / glass), 会拉低 Remotion 性能, 且难以同步字幕.
- 不要用 AGPL 代码 (如 OmniVoice), 必须隔离部署.
- 不要为了“贴近 Fliki 原生”主动引入 Next.js / Streamlit / Bun, 与本机 Node 24 + Vite/React 19 体系冲突.

---

## 6. 参考资料

- 本机实现: backend/workers/remotion-project/src/Main.tsx
- Avatar 浮层参数: docs/audit-p5d7.md (未创建, 未来归汇到本文件)
- Pixelle VideoTransitionMode 倒入参考: docs/DOWNLOAD_AUDIT.md
- 安全区测试: backend/tests/test_p5d7_avatar_layout.py
