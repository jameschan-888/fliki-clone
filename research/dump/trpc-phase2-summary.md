# Phase 2 补抓摘要 — Style Library + Sample Prompts

> 抓取时间: 2026-07-23 | 工具: Chrome DevTools MCP + 浏览器内 fetch → Blob download → D:\workspace
> 数据源: tRPC batch endpoint (style.list, mediaMy.listSamples)

---

## 1. Style 库 (29 个完整 style)

每个 style 包含字段: `_id` / `name` / `key` / `prefix` / `suffix` / `characterPrompt` / `composition` / `thumbnail` / 17 个含 `imagePromptDirection` + `videoPromptDirection`

| # | name | key |
|---|------|-----|
| 1 | 3D model | `3dModel` |
| 2 | 70s Documentary | `70sDocumentary` |
| 3 | Anime | `anime` |
| 4 | Biblical | `biblical` |
| 5 | Brush ink | `brushInk` |
| 6 | Chalkboard | `chalkboard` |
| 7 | Charcoal | `charcoal` |
| 8 | Cinematic | `cinematic` |
| 9 | Clay | `modelingCompound` |
| 10 | Comic book | `comicBook` |
| 11 | Crayon | `crayon` |
| 12 | Fantasy art | `fantasyArt` |
| 13 | Film noir | `filmNoir` |
| 14 | Golden age | `goldenAge` |
| 15 | Golden hour | `goldenHour` |
| 16 | Illustration | `illustration` |
| 17 | Layered papercut | `layeredPapercut` |
| 18 | Lego | `lego` |
| 19 | Line art | `lineArt` |
| 20 | Neon noir | `neonNoir` |
| 21 | Paper cutout | `paperCutout` |
| 22 | Pencil sketch | `pencilSketch` |
| 23 | Realistic | `realistic` |
| 24 | Renaissance | `renaissance` |
| 25 | Stick figure | `stickFigure` |
| 26 | Technical illustration | `technicalIllustration` |
| 27 | Tiny world | `tinyWorld` |
| 28 | Watercolor | `watercolor` |
| 29 | Whimsical | `whimsical` |

### 1.1 完整 prefix/suffix 对照 (29 个)

```
3dModel ::
  P: Pixar-style 3D animation, expressive design, warm cinematic lighting,
  S: polished CGI, vibrant colors, theatrical quality
70sDocumentary ::
  P: Cold War espionage cinematic, heavy 16mm film grain, desaturated olive and grey palette, gritty documentary realism,
  S: handheld camera instability suggestion, harsh practical lighting, period-accurate texture, paranoid tight framing, 1960s Eastern European atmosphere
anime ::
  P: 1990s OVA anime aesthetic, sharp cel outlines, retro color palette,
  S: grainy film texture, dramatic highlights, nostalgic shading style
biblical ::
  P: dramatic biblical painting style, divine lighting, sacred atmosphere,
  S: renaissance religious art, heavenly radiance, spiritual grandeur
brushInk ::
  P: brush ink illustration, expressive brush stroke quality, black ink on white, wet brush to dry brush range, calligraphic energy,
  S: ink stroke variation from thick to thin, dry brush texture marks, pooled ink in shadow areas, white space as light, gestural brush energy
chalkboard ::
  P: chalk blackboard drawing animation, hand-drawn chalk lines, blackboard green-black surface texture, chalk dust and smear texture, white and colored chalk,
  S: chalk dust particle overlay, smeared chalk shadow areas, blackboard surface grain, hand-drawn imperfection, classroom aesthetic
charcoal ::
  P: charcoal illustration, powdery charcoal texture, dramatic tonal contrast, smudged shadow areas, bold dark marks on textured paper,
  S: charcoal dust particle quality, eraser light marks, deep black charcoal shadows, rough paper texture visible, expressive gestural mark making
cinematic ::
  P: cinematic film still
  S: shallow depth of field, vignette, highly detailed, high budget, bokeh, cinemascope, moody, epic, gorgeous, film grain, grainy
modelingCompound ::
  P: stop-motion claymation style, handcrafted clay figures, tactile texture,
  S: visible fingerprints, soft plasticine aesthetic, charming handmade quality
comicBook ::
  P: Western comic-book illustration, bold outlines, graphic dramatic style,
  S: halftone shading, vivid flat colors
crayon ::
  P: wax crayon illustration, heavy press crayon strokes, paper grain visible through color, waxy texture layer, child art energy,
  S: uneven color fill pressure, white paper gaps in color zones, thick waxy outline, saturated primary crayon palette, crayon stroke direction visible
fantasyArt ::
  P: ethereal fantasy concept art of
  S: magnificent, celestial, ethereal, painterly, epic, majestic, magical, fantasy art, cover art, dreamy
filmNoir ::
  P: film noir style
  S: monochrome, high contrast, dramatic shadows, 1940s style, mysterious, cinematic
goldenAge ::
  P: golden age sci-fi illustration, oil on canvas, painterly brushwork, retro 1950s pulp art,
  S: rich impasto texture, dramatic chiaroscuro, saturated primary colors, classic composition, museum quality
goldenHour ::
  P: golden hour painterly realism, warm amber and rose light, soft impressionistic oil texture, long raking shadows,
  S: visible brushstroke texture overlay, luminous skin tones, hazy atmospheric perspective, warm color grade, cinematic stillness
illustration ::
  P: Digital Illustration
  S: 
layeredPapercut ::
  P: stacked papercut art of
  S: 3D, layered, dimensional, depth, precision cut, stacked layers, papercut, high contrast
lego ::
  P: Lego brick animation, ABS plastic surface rendering, visible stud grid geometry, primary color brick construction, hard edge plastic aesthetic,
  S: plastic sheen highlight, brick seam lines visible, constructed environment aesthetic, bold primary palette, toy production render quality
lineArt ::
  P: clean line art illustration, precise contours, minimal shading,
  S: crisp linework, elegant simplicity, technical drawing aesthetic
neonNoir ::
  P: neon noir ultrarealistic cinematic, rain-slicked streets, deep chiaroscuro lighting, cyan and magenta neon reflections,
  S: dramatic volumetric fog, shallow depth of field, ultra-sharp foreground detail, photorealistic film grain, 4K cinematic
paperCutout ::
  P: paper cutout animation, layered flat paper texture, visible drop shadow between layers, torn and scissor cut edges, flat color paper fill,
  S: cardstock surface texture, layered depth through shadow, flat color zones, handmade paper aesthetic, South Park adjacent visual language
pencilSketch ::
  P: graphite pencil sketch, grey pencil tonal range, visible pencil stroke texture, white paper ground, hatching and shading marks,
  S: smudged graphite shadow areas, eraser highlight marks, pencil stroke direction visible, full tonal range from white to deep graphite, sketch energy
realistic ::
  P: A cinematic photograph, natural lighting
  S: high contrast, professional photo, sharp focus
renaissance ::
  P: Renaissance oil painting chiaroscuro, single warm candlelight source, Rembrandt lighting, deep rich shadow,
  S: cracked oil paint varnish texture, warm amber and umber tones, soft sfumato edges, dramatic tenebrism, masterwork composition
stickFigure ::
  P: hand-drawn black marker doodle illustration on white whiteboard, minimalist stick figure style,
  S: flat 2D hand-drawn black marker doodle on plain white whiteboard, thick uneven black ink outlines, marker linework, rough pencil hatching only, no shading gradients, single red accent used only for arrows underlines and simple shapes, no written text, no letters, no words, no captions, pure flat white background, no environment, no realistic textures, no photographic detail, no photograph, no photorealism, no real lighting, no sunlight, no fluorescent light, no haze, no depth of field, no foreground background layering, whiteboard explainer aesthetic, consistent line weight, no watermark, no logo
technicalIllustration ::
  P: precise technical illustration, blueprint aesthetic, clean diagrams,
  S: schematic detailing, engineering drawing style, measured accuracy
tinyWorld ::
  P: miniature diorama scene, tilt-shift photography effect, tiny detailed world,
  S: selective focus, toy-like scale, shallow depth of field, whimsical miniaturization
watercolor ::
  P: watercolor painting
  S: vibrant, beautiful, painterly, detailed, textural, artistic
whimsical ::
  P: Studio Ghibli-style hand-painted fantasy aesthetic with gentle storytelling atmosphere,
  S: soft painterly lighting, warm palettes, lush environmental detail
```

### 1.2 imagePromptDirection 非空 style (2 个)

**Cinematic** (`cinematic`)
- image: "High-budget cinematic film still with professional composition and dramatic lighting."
- video: "Slow cinematic tracking shots, shallow depth of field, dramatic lighting changes, epic atmosphere."

**Golden age** (`goldenAge`)
- image: "Every scene is rendered with visible, expressive oil brushwork evoking mid-century pulp science fiction cover art. Colors are bold and saturated — deep cobalt blues, burnt oranges, chrome silvers. Lighting is theatrical and dramatic, with heroic figures bathed in warm foreground light against vast cosmic darkness. Texture is physical and tactile, with thick paint strokes defining form."
- video: 同 image（heroic figures bathed in warm foreground light against vast cosmic darkness）

**关键工程映射**：`style.key` 直接喂给 LLM 作为 `imageStyle` / `videoStyle` 字段。`prefix`+`suffix` 自动拼到 prompt 头尾。`imagePromptDirection`/`videoPromptDirection` 是补充 meta-prompt，仅 2 个 style 有。

### 1.3 characterPrompt 范式 (12+ style 有)

每个 characterPrompt 是 LLM meta-instruction，强制 7 段 telegraphic 描述：

1. Demographics (integer age + gender + ethnicity)
2. Skin/Coloring (tone + 1-2 surface details)
3. Build/Proportions (style-specific)
4. Facial Features (style-specific signature)
5. Hair (color + texture + style)
6. Clothing (color + fabric/garment + 1 detail)
7. Accessories (1-2 items)

**Ban 列表通用**：subjective adjectives / emotional expressions / verbs / narrative context / generic categories。

**工程实现**：在 `script_to_video.py` 节点加 `style.characterPrompt` 注入到 LLM system prompt，强制 LLM 输出合规角色描述。

---

## 2. Image Sample Prompts (50 个)

### 2.1 模型分布

| 模型 | 次数 |
|------|------|
| `runware-gpt-image-2` | 7 |
| `runware-z-image-turbo` | 43 |

**默认 = `runware-z-image-turbo`** (43/50 = 86%)
次选 = `runware-gpt-image-2` (7/50 = 14%)

### 2.2 第一个 sample 完整 prompt (image)

```
"prompt":"A mixed-race man in his early thirties with light brown skin, neatly trimmed beard, wearing a paint-flecked grey hoodie, stands in front of a half-finished oil painting on an easel in a sunlit home studio, looks at camera and says with a tired smile, \"Okay <umm> day forty-seven. <chuckle> The eyes are still wrong. <sigh> But I think I finally see it now.\" Selfie phone framing, warm afternoon backlight, raw studio aesthetic. SFX: distant traffic, a brush dropped on a wooden palette, a deep exhale, faint ambient lo-fi music from a speaker off-frame."
```

**Prompt 范式 (image sample)**：

- 主体描述 (character + clothing + setting + framing)
- 镜头/光 (Selfie phone framing, warm afternoon backlight, raw studio aesthetic)
- **TTS 标签嵌入 dialogue**: `<umm>` `<chuckle>` `<sigh>` 包围在引号 dialogue 内
- **SFX 行**: `SFX: distant traffic, ...` 列出声效/环境音

### 2.3 Aspect Ratio 分布 (5 种)

`16:9` (默认) / `9:16` (vertical) / `4:7` (portrait) / `1:1` (square) / `7:4` (wide cinematic)

**工程默认值**: `16:9` → `1536x1024` 像素（已在 v6 决策表登记）

---

## 3. Video Sample Prompts (50 个)

### 3.1 模型分布 (9 个 video model)

| 模型 | 次数 | 用途 |
|------|------|------|
| `runware-kling-3-pro` | 7 | 高质量主推 |
| `runware-seedance-pro-fast` | 7 | 速度优先 |
| `runware-pixverse-v5-fast` | 7 | 通用 |
| `runware-p-video` | 7 | 通用 |
| `runware-happyhorse-v1` | 7 | 写实风格 |
| `runware-ltx-2-fast` | 6 | 速度优先 |
| `runware-p-video-avatar` | 4 | 数字人 (avatar) |
| `runware-omnihuman-1-5` | 3 | 数字人 (human) |
| `runware-kling-2.5-turbo` | 2 | 备选 |

**默认 = `runware-kling-3-pro`** (7/50 = 14%, 与其它 6 模型并列最高频)
**数字人专用 = `runware-p-video-avatar` (4) + `runware-omnihuman-1-5` (3) = 7 个 sample 用了数字人模型**

### 3.2 第一个 video sample 完整 prompt

```
"prompt":"A couple (lock from references) walks hand in hand along a cliffside path overlooking the Mediterranean at sunset, slow aerial side-tracking shot following them, golden hour palette, cinematic travel-film grade, soft haze, 2.39:1 framing. SFX: distant waves, light wind, a single ambient acoustic guitar. Maintain both character identities throughout."
```

**Prompt 范式 (video sample)**：

- 主体动作 (A couple walks hand in hand)
- **镜头运动**: "slow aerial side-tracking shot following them"
- **光影/调色**: "golden hour palette, cinematic travel-film grade, soft haze"
- **画幅**: "2.39:1 framing"
- **SFX**: 声效/环境音 (与 image 同样有 SFX 行)
- **角色一致性提示**: "Maintain both character identities throughout" (lock from references)

### 3.3 第一个 avatar sample prompt

```
"prompt":"Steady, dignified delivery, one calm gesture with the right hand mid-sentence, soft natural pause on \"Not just our partners\", warm closing smile, slow blinks, gravitas in the closing pause."
```

**Avatar prompt 范式**：动作 + 表情 + 节奏（slow blinks / soft pause）描述，不描述外观（用 reference 图）。

### 3.4 Aspect Ratio + Quality

- AR: `16:9` (默认) / `2:3` / `1:1` / `20:11` / `9:16` / `11:20` / `3:4` / `22:39` (竖屏) / `39:22` (横屏) / `NaN:NaN` (1 个 avatar)
- Quality: `720p` + `1080p` (默认 1080p)
- Default 输出: 1920x1080 (16:9) / 1080x1920 (9:16)

---

## 4. 工程落地清单 (Phase 2 后)

### 4.1 数据库新增表

```sql
CREATE TABLE styles (
  _id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  key TEXT UNIQUE NOT NULL,
  prefix TEXT,
  suffix TEXT,
  character_prompt TEXT,
  composition TEXT,
  image_prompt_direction TEXT,
  video_prompt_direction TEXT,
  thumbnail TEXT,
  is_enabled BOOLEAN DEFAULT 1
);

CREATE TABLE media_samples (
  _id TEXT PRIMARY KEY,
  type TEXT,  -- image / video
  file_path TEXT,
  name TEXT,
  duration REAL,
  aspect_ratio TEXT,
  quality TEXT,
  model TEXT,
  style TEXT,
  prompt TEXT,
  thumbnail TEXT,
  is_playground_generated BOOLEAN
);
```

### 4.2 LLM 节点 prompt 模板（script_to_video）

```
# scene_breakdown prompt
Given the user script and chosen style, decompose into N scenes.
Each scene must have:
  - subject (character + outfit)
  - setting (location + time of day)
  - action (movement + camera)
  - dialogue (in quotes, with <umm>/<chuckle>/<sigh> tags)
  - sfx (one line, list of ambient sounds)
  - framing (shot type + light + grade)
Style: {style.name}
Style prefix: {style.prefix}
Style suffix: {style.suffix}
If style has characterPrompt, follow its 7-section format.
```

### 4.3 节点 API 配置 (决策 5)

| 节点 | 模型 (默认) | 备选 | API 配置字段 |
|------|-------------|------|--------------|
| `sceneBreakdown` | `gemini-2.5-flash-lite` | `gpt-4o-mini` | `SCENE_BREAKDOWN_API_KEY` |
| `imageGen` | `runware-z-image-turbo` | `runware-gpt-image-2` | `RUNWARE_API_KEY` |
| `videoGen` | `runware-kling-3-pro` | 8 备选 model | `RUNWARE_API_KEY` |
| `avatarGen` | `runware-p-video-avatar` | `runware-omnihuman-1-5` | `RUNWARE_API_KEY` |
| `tts` | Edge TTS | `GPT-SoVITS` (本地) | (Edge TTS 无 key) |
| `musicGen` | MiniMax Music 2.6 | `runware-music` | `MINIMAX_API_KEY` / `RUNWARE_API_KEY` |

### 4.4 TTS 标签预处理 (Phase 2 新增)

在 TTS 节点前加 preprocessing：
- `<umm>` → 注入 SSML `<break time="200ms"/>` 或作为 prosody 提示
- `<chuckle>` → 注入 SSML `<prosody rate="fast" pitch="+10%">`
- `<sigh>` → 注入 SSML `<prosody volume="-20%"><break time="500ms"/></prosody>`

Edge TTS 支持 SSML，GPT-SoVITS 走 text 预处理（标记转 token）。

### 4.5 数字人本地化 (决策 6 升级)

`runware-p-video-avatar` + `runware-omnihuman-1-5` 都走 Runware API（付费）。本地化方案：

| Runware 付费 | 本地替代 |
|--------------|----------|
| `p-video-avatar` | **SadTalker** (单图+音频) |
| `p-video-avatar` (高质量) | **MuseTalk** (实时, 视频驱动) |
| `omnihuman-1-5` | **MuseTalk** + **AnimateAnyone** |
| `omnihuman-1-5` (动作迁移) | **AnimateDiff** + ControlNet |

`avatars` driver 表改成本地模型池：
```python
AVATAR_DRIVERS = {
  "sadTalker": "本地化数字人 (单图+音频, 8GB VRAM)",
  "museTalk": "本地化数字人 (实时, 需 12GB+ VRAM)",
  "animateDiff": "动作迁移 (通用)",
}
```

---

## 5. Phase 3 待补

- [ ] `preview.detail` schema: 用户跑通 Share preview 流程后用 previewId fetch（当前 null）
- [ ] `render.latest` response schema: 触发 render job 阻塞等结果再抓（当前 200 但 response 未抓）
- [ ] 5 个 + 50 个 + 50 个 prompt 全文已在 dump JSONL，验证用 1k tokens 取样
- [ ] Runware 各 model 定价调研（9 video model 成本差异大）
- [ ] Edge TTS 80+ 语言支持矩阵（v6 已定）
