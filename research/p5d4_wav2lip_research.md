# P5D-4 Wav2Lip-ONNX 集成调研

> 调研日期：2026-07-24  
> 目标机器：Intel Iris Xe、8 核 CPU、15.8GB RAM、无 NVIDIA GPU  
> 结论：P5D-4 首选轻量 Wav2Lip-ONNX，静态头像作为强制兜底；LivePortrait-AudioDriven 暂不进入本机主链路。

## 1. 结论先行

1. **推荐主方案：instant-high/wav2lip-onnx 轻量链路。** 它明确支持 CPU、无需 PyTorch，单个 Wav2Lip ONNX 模型约 145MB；当前机器已有 onnxruntime 1.27.0、FFmpeg 和 OpenCV，补 librosa 后即可进入实测。
2. **高质量版只作为第二阶段可选增强。** wav2lip-onnx-HQ 增加人脸对齐、遮挡、增强、降噪等多个 ONNX 模型，会显著增加下载量、内存和 CPU 时间；上游只给“CPU 可运行”，没有可复现的 CPU FPS。
3. **LivePortrait-AudioDriven 暂缓。** 它要求 LivePortrait 基础权重、Whisper Tiny、自定义音频关键点模型和统计文件，依赖文件明确包含 onnxruntime-gpu，README 以 CUDA 环境为主，并且没有提供开箱即用的音频驱动预训练模型下载入口。

## 2. 证据等级

- **已验证：** 仓库 README、requirements、代码、GitHub/Hugging Face API 返回的数据。
- **本机已验证：** 原型在模型不存在时，使用 FFmpeg 生成 H.264 + AAC MP4；1.2 秒、320×320 测试文件用时 0.188 秒。
- **待验证：** Intel Iris Xe 机器上的真实 ONNX FPS、峰值内存、长音频稳定性。上游没有给 CPU 型号、分辨率、FPS、批量大小齐全的基准，不能把“quite fast”当成性能承诺。

## 3. 选型对比

| 方案 | 模型与依赖 | CPU 速度 | 质量与能力 | 输入 / 输出 | License / 商用 | Windows | 结论 |
|---|---|---|---|---|---|---|---|
| Wav2Lip-ONNX 轻量版 | 单个模型约 145MB；约 3.29MB SCRFD；onnxruntime、OpenCV、NumPy、librosa、FFmpeg | 上游只称 CPU “quite fast”，没有可信 FPS；第 1 周实测 | 只改嘴部，不含对齐、修复、增强 | 图片/视频 + 音频；96×96 六通道人脸 + 80×16 mel；输出 MP4 | 仓库无独立 LICENSE；原始权重只允许研究/学术/个人用途，禁止商用 | 高 | **首选 MVP** |
| Wav2Lip-ONNX-HQ | 轻量模型 + 检测/识别/对齐/解析/增强/遮挡/降噪等多个 ONNX；至少数百 MB | 上游称 CPU 可运行，但无 CPU 基准；增强器继续拖慢 | 头部角度、人脸融合、遮挡和清晰度更好 | 图片/视频 + 驱动音频，可选目标脸、双音频、循环和增强 | 仓库无独立 LICENSE；继承 Wav2Lip 非商用权重风险，各模型需逐项审计 | 可运行但复杂 | **后续可选** |
| LivePortrait-AudioDriven | LivePortrait HF 权重集合约 3.61GB（含人/动物）；另需 Whisper Tiny、自定义 predictor、statistic.pt、PyTorch、transformers、onnxruntime-gpu | README 称低延迟/实时，但没有 CPU 数据；依赖和安装面向 CUDA | 可生成表情和头部动作，质量上限更高 | 单张人脸 + 音频；默认 30 FPS 视频 | 代码 MIT；InsightFace 模型只限非商用研究，商用需替换 | 不是 CPU/Windows 开箱方案 | **当前不选** |
| 静态头像 fallback | 0 模型；只需 FFmpeg | 本机短样本约 6.4× 实时，仅作兜底参考 | 无口型，只保证交付 | 图片 + FFmpeg 可解码音频；H.264/AAC MP4 | 取决于输入素材权利 | 最高 | **强制保留** |

## 4. Wav2Lip-ONNX 集成细节

### 4.1 模型大小

- Hugging Face bluefoxcreation/Wav2lip-Onnx 包含 wav2lip.onnx 与 wav2lip_gan.onnx，API 返回总存储量 290,350,942 字节，因此单个模型约 145MB。
- instant-high/wav2lip-onnx 仓库自带 scrfd_2.5g_bnkps.onnx，GitHub Tree API 显示为 3,290,207 字节。
- MVP 只放一个 wav2lip.onnx，加检测器后模型目录约 149MB，不下载两个 Wav2Lip 变体。

### 4.2 上游依赖

轻量仓库 requirements：

```text
opencv-python==4.8.0.76
numpy
tqdm
librosa
numba
insightface==0.2.1
onnxruntime
```

本项目原型分两层：

- **静态 fallback：** Python 标准库 + FFmpeg，模型和 AI 依赖全部可缺失。
- **ONNX 推理：** NumPy + OpenCV + librosa + onnxruntime。原型先用 OpenCV Haar 检测器减少模型依赖；正式版建议换上游 3.29MB SCRFD，提升侧脸和弱光稳定性。

### 4.3 输入、预处理、输出

上游 inference_onnxModel.py 的实际合同：

1. 音频经 FFmpeg 转 16kHz 单声道 WAV。
2. 音频转 80 维 mel 频谱，每帧取 80×16 切片。
3. 检测人脸，裁剪后缩放为 96×96。
4. 下半张脸置零，与原脸拼为 6 通道，得到 N×6×96×96。
5. mel 输入为 N×1×80×16。
6. 常见输入名为 mel_spectrogram 和 video_frames，输出为 N×3×96×96。
7. 把预测结果贴回原帧，再与音频合成 H.264/AAC MP4。

原型支持静态图片；正式版若接输入视频，需要补帧读取、逐帧检测平滑、ping-pong/loop 和多脸选择。

### 4.4 CPU 性能判断

- 上游只有“CPU 上 quite fast”的定性描述，没有可复现测试数据。
- 人脸检测、每音频帧一次 96×96 ONNX 推理、全分辨率编码是主要耗时点。
- 下载模型前不能承诺实时。第 1 周必须记录 10 秒/30 秒音频耗时、推理 FPS、峰值 RSS 和音画误差。
- 建议验收线：30 秒、720p 静态头像在 5 分钟内完成；若超时则自动降级静态头像，不阻塞工作流。

## 5. 模型下载与目录

统一目标路径：

```text
backend/data/wav2lip/wav2lip.onnx
```

原型按以下顺序尝试下载，但默认关闭，避免本次实际拉取 100MB+ 文件：

1. ModelScope 社区镜像：<https://www.modelscope.cn/models/cjc1887415157/facefusion-assets/resolve/master/wav2lip_gan.onnx>
2. Hugging Face：<https://huggingface.co/bluefoxcreation/Wav2lip-Onnx/resolve/main/wav2lip.onnx>
3. GitHub Release：<https://github.com/facefusion/facefusion-assets/releases/download/models/wav2lip_gan.onnx>
4. 上游 Google Drive：<https://drive.google.com/file/d/1_l4QC2RJ9nXapSQRD61-Q4KbSApc53HM/view>

这些都是社区分发，不代表获得新商用授权。下载后应记录 SHA-256；正式发布前锁定已审计哈希，避免镜像静默换包。

启用自动下载：

```text
FLIKI_WAV2LIP_AUTO_DOWNLOAD=1
```

也可显式调用 download_model()；本次未执行。

## 6. 挂接现有 avatar provider

当前 backend/providers/base.py 只有 Stock/TTS/Music 三个 ABC。本次不改现有代码，避免准备任务提前改变合同。正式 P5D-4 建议：

1. 在 providers/base.py 新增 AvatarProvider.synthesize(face_image_path, audio_path, destination_path) -> dict。
2. 把本原型包装为 providers/avatar/wav2lip_onnx.py，注册 provider key wav2lip_onnx。
3. 增加 static_avatar provider，复用同一个 FFmpeg fallback，允许配置层直接选择。
4. provider_configs.node_type=avatar 保存模型路径、超时、FPS、是否允许下载和 fallback 顺序。
5. 工作流节点只传头像 asset id 和旁白 asset id；provider 解析路径，输出写入现有 workflow run 目录。
6. 统一返回 status、provider、mode、output_path、fallback_used、reason、elapsed_seconds，方便 UI 显示降级原因。

推荐降级链：

```text
wav2lip_onnx -> wav2lip_onnx_hq（仅手动开启） -> static_avatar
```

LivePortrait-AudioDriven 不放进当前机器自动链路，只保留未来 NVIDIA/云端 provider 插槽。

## 7. 风险与回退

| 风险 | 判断 | 回退策略 |
|---|---|---|
| 模型不存在或镜像失败 | 常见，镜像会变更 | 默认不下载；失败立即静态头像 |
| 缺 librosa/OpenCV 或版本冲突 | 当前本机缺 librosa | 捕获异常并静态降级；第 1 周锁依赖 |
| 无法检测人脸 | 侧脸、遮挡、低清常见 | 静态降级；正式版换 SCRFD，UI 提示换正脸图 |
| CPU 太慢或内存高 | 尚未实测 | avatar 节点硬超时；终止后静态降级 |
| 音画不同步 | mel 帧数、FPS、音频长度影响 | 固定 25 FPS，FFmpeg -shortest，ffprobe 校验 |
| 嘴部模糊/边缘明显 | 轻量版无增强对齐 | 先改善输入和裁剪；HQ 只作可选增强 |
| 商用授权不清 | Wav2Lip 原权重明确非商用 | MVP 标记研究测试；商用前换合规权重/API或重训 |
| InsightFace 授权 | 模型仅限非商用研究 | 商用时替换检测器并单独审计 |
| GPU-only 方案误选 | 当前机器不可用 | 无 CUDA 时隐藏默认选项，走 ONNX/静态 |
| 肖像权与冒用 | 数字人天然有风险 | 保存授权记录，限制无权头像/声音，标记 AI 生成 |

## 8. 原型说明

文件：backend/wav2lip_prototype.py

已实现：

- Wav2LipProvider 与 synthesize(face_image_path, audio_path, destination_path) -> dict。
- 检查固定模型路径。
- 可选 ModelScope/Hugging Face/GitHub Release 下载，临时文件完成后原子替换并返回 SHA-256。
- ONNX Runtime CPU Session、音频预处理、人脸检测、96×96 口型推理、回贴和 MP4 合成骨架。
- 模型、依赖、人脸检测、推理或下载任一环节失败时，自动用 FFmpeg 合成静态头像视频。
- FFmpeg 首选 libx264，失败再尝试 mpeg4；方法不向上抛异常，而返回结构化失败信息。

本次 smoke test：

- 输入：320×320 测试图 + 1.2 秒 16kHz WAV。
- 模型：不存在，未触发下载。
- 结果：status=success、mode=static_avatar、H.264 视频 + AAC 音频、时长 1.2 秒。

## 9. P5D-4 三周路线图

### 第 1 周：模型与 CPU 基线

- 手动下载并锁定 wav2lip.onnx SHA-256，不同时下载多个变体。
- 安装/锁定 librosa 兼容版本，验证 Python 3.12 + onnxruntime 1.27。
- 跑通正脸图片 + 10 秒、30 秒中文音频，记录耗时、FPS、峰值内存和音画误差。
- 将 Haar 检测替换为 3.29MB SCRFD，补无脸、坏音频、坏模型、超时、fallback 测试。
- 验收：ONNX 成功和全部失败分支都能输出可播放 MP4 或结构化错误，不拖垮 worker。

### 第 2 周：接入 avatar provider

- 增加 AvatarProvider ABC 和 providers/avatar 注册，不改变 Stock/TTS/Music 行为。
- 接入 provider config、工作流 avatar 节点、输出资产登记和重试。
- 加硬超时、临时目录清理、模型单例 session、并发锁和内存监控。
- 做 Script-to-video → TTS → Avatar → Remotion 端到端测试。
- 验收：无模型、无脸、推理超时都自动降级，主工作流仍成功。

### 第 3 周：UI 与多模型 fallback

- 加数字人选择面板：头像、模型、质量档位、预计耗时、授权提示。
- UI 展示实际执行模式：Wav2Lip、HQ 可选、静态降级及原因。
- CPU 基线达标后试验 HQ 的对齐/增强单模块，不一次开启全套。
- 为未来 NVIDIA/云端 LivePortrait/MuseTalk provider 保留能力字段，但本机禁用。
- 验收：用户可预览、切换、重试；任何模型不可用时仍能导出视频。

## 10. 待跟进决策

1. **商用边界：** 如果项目要商业发布，现有 Wav2Lip 开源权重不能直接作为生产默认，需选择有商用授权的权重/API或重训。
2. **性能阈值：** 第 1 周实测后再决定 30 秒任务硬超时，当前 5 分钟只是保守验收线。
3. **质量档位：** 轻量版稳定前不要同时引入 HQ 多个增强模型，先逐模块量化收益和耗时。

## 11. 主要来源

- 轻量仓库：<https://github.com/instant-high/wav2lip-onnx>
- 轻量推理代码：<https://raw.githubusercontent.com/instant-high/wav2lip-onnx/main/inference_onnxModel.py>
- 轻量 requirements：<https://raw.githubusercontent.com/instant-high/wav2lip-onnx/main/requirements.txt>
- 轻量仓库文件大小：<https://api.github.com/repos/instant-high/wav2lip-onnx/git/trees/main?recursive=1>
- Wav2Lip 原仓库与非商用声明：<https://github.com/Rudrabha/Wav2Lip>
- Hugging Face ONNX：<https://huggingface.co/bluefoxcreation/Wav2lip-Onnx>
- ModelScope 镜像：<https://www.modelscope.cn/models/cjc1887415157/facefusion-assets>
- HQ 仓库：<https://github.com/instant-high/wav2lip-onnx-HQ>
- LivePortrait-AudioDriven：<https://github.com/Hekenye/LivePortrait-AudioDriven>
- LivePortrait-AudioDriven LICENSE：<https://raw.githubusercontent.com/Hekenye/LivePortrait-AudioDriven/main/LICENSE>
- LivePortrait 权重 API：<https://huggingface.co/api/models/KlingTeam/LivePortrait>
