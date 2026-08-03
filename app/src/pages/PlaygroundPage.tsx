import { useState } from "react";
import { Footer } from "../components/layout/Footer";

const TYPES = ["Image", "Video", "Music"] as const;
const SUBTABS = ["Create", "Edit", "Upscale", "Remove BG"] as const;

type GenType = typeof TYPES[number];
const MODELS: Record<GenType, Array<{ id: string; name: string; credits: number; desc: string }>> = {
  Image: [
    { id: "flux2klein", name: "Flux 2 Klein", credits: 0.05, desc: "Sub-second 开源生成, 支持 multi-reference 编辑" },
    { id: "gptimage2", name: "GPT Image 2", credits: 0.08, desc: "文字渲染 + 多画幅, 缩略图首选" },
    { id: "fluxpro", name: "Flux Pro", credits: 0.12, desc: "高保真写实, 适合产品图" },
    { id: "qwen", name: "Qwen-Image-Edit-Plus", credits: 0.06, desc: "中文 prompt 优化, 编辑能力强" },
    { id: "nanobanana2", name: "Nano Banana 2", credits: 0.04, desc: "轻量快速, 适合草图" },
    { id: "seedream45", name: "Seedream 4.5", credits: 0.07, desc: "字节系, 多画幅 + 文字渲染" },
  ],
  Video: [
    { id: "veo31", name: "Veo 3.1", credits: 0.30, desc: "Google 1080p, 多镜头 + 真人级" },
    { id: "sora2", name: "Sora 2", credits: 0.50, desc: "OpenAI 长镜头, 物理真实" },
    { id: "kling3pro", name: "Kling 3 Pro", credits: 0.25, desc: "快手 5s 720p, 性价比" },
    { id: "runware", name: "Runware", credits: 0.20, desc: "通用 4s 480p, 速度优先" },
  ],
  Music: [
    { id: "suno", name: "Suno v4", credits: 0.15, desc: "30s 完整歌曲, 歌词 + 人声" },
    { id: "udio", name: "Udio", credits: 0.18, desc: "高保真, 多风格" },
    { id: "mubert", name: "Mubert", credits: 0.05, desc: "无限 BGM, 商用授权" },
  ],
};

const STYLES = ["Cinematic", "Photorealistic", "Anime", "Watercolor", "3D Render", "Pixel Art"];
const ASPECTS = ["16:9", "9:16", "1:1", "4:5"];

type HistoryItem = { id: string; type: GenType; model: string; prompt: string; ts: string; credits: number };

export function PlaygroundPage() {
  var _t = useState<GenType>("Image"), type = _t[0], setType = _t[1];
  var _s = useState("Create"), sub = _s[0], setSub = _s[1];
  var _p = useState(""), prompt = _p[0], setPrompt = _p[1];
  var _m = useState<string>(MODELS.Image[0].id), model = _m[0], setModel = _m[1];
  var _a = useState("16:9"), aspect = _a[0], setAspect = _a[1];
  var _st = useState("Cinematic"), style = _st[0], setStyle = _st[1];
  var _r = useState<string[]>([]), refs = _r[0], setRefs = _r[1];
  var _h = useState<HistoryItem[]>([
    { id: "h1", type: "Image", model: "Flux 2 Klein", prompt: "咖啡冲泡特写, 暖色调, 8K", ts: "2026-08-01", credits: 0.05 },
    { id: "h2", type: "Video", model: "Veo 3.1", prompt: "森林 B-roll 10s, 早晨光", ts: "2026-07-30", credits: 0.30 },
  ]), history = _h[0], setHistory = _h[1];
  var _b = useState(false), busy = _b[0], setBusy = _b[1];
  var _e = useState<string | null>(null), enhancedPrompt = _e[0], setEnhancedPrompt = _e[1];

  var modelsForType = MODELS[type];
  var currentModel = modelsForType.find(function (m) { return m.id === model; }) || modelsForType[0];

  function changeType(t: GenType) {
    setType(t);
    var first = MODELS[t][0];
    setModel(first.id);
    setSub("Create");
    setRefs([]);
    setEnhancedPrompt(null);
  }

  function enhancePrompt() {
    if (!prompt.trim()) return;
    setBusy(true);
    setTimeout(function () {
      var enhanced = prompt + " · " + style + " style, " + aspect + " aspect ratio, high detail, professional composition, 8K resolution";
      setEnhancedPrompt(enhanced);
      setBusy(false);
    }, 600);
  }

  function addRef() {
    if (refs.length >= 4) return;
    setRefs(refs.concat(["ref-" + Date.now() + ".png"]));
  }

  function generate() {
    if (!prompt.trim()) return;
    setBusy(true);
    setTimeout(function () {
      var next: HistoryItem = {
        id: "h-" + Date.now(),
        type: type,
        model: currentModel.name,
        prompt: enhancedPrompt || prompt,
        ts: new Date().toISOString().slice(0, 10),
        credits: currentModel.credits,
      };
      setHistory([next].concat(history));
      setBusy(false);
    }, 1200);
  }

  function modelPicker() {
    return (
      <select value={model} onChange={function (e) { setModel(e.target.value); }}>
        {modelsForType.map(function (m) { return (
          <option key={m.id} value={m.id}>{m.name} · {m.credits} credits</option>
        ); })}
      </select>
    );
  }

  return (
    <main className="shell">
      <h1>Playground</h1>
      <p className="lead">AI 图像/视频/音乐生成 + 编辑统一入口. 支持 6+ 主流模型, 风格/画幅/参考图全控制.</p>

      <div className="typePick" role="tablist">
        {TYPES.map(function (t) { return (
          <button key={t} className={type === t ? "active" : ""} onClick={function () { changeType(t); }}>{t}</button>
        ); })}
      </div>

      <div className="subTabs">
        {SUBTABS.map(function (s) { return (
          <button key={s} className={sub === s ? "active" : ""} onClick={function () { setSub(s); }}>{s}</button>
        ); })}
      </div>

      <div className="playGrid">
        <div className="panel">
          <h3>{sub} · {type}</h3>

          <label>Prompt</label>
          <textarea placeholder={type === "Music" ? "Lo-fi piano, 90 BPM, 适合读书" : type === "Video" ? "早晨森林 4K B-roll, 雾气, 10s" : "咖啡冲泡特写, 暖色调, 蒸汽, 8K"} value={prompt} onChange={function (e) { setPrompt(e.target.value); }} />
          <div className="enhanceRow">
            <button onClick={enhancePrompt} disabled={busy || !prompt.trim()}>✨ Enhance (AI 改写)</button>
            {enhancedPrompt && <small style={{ color: "#48d58b", fontSize: 11 }}>已增强</small>}
          </div>
          {enhancedPrompt && <div className="meta" style={{ marginTop: 6, padding: 8, background: "rgba(72,213,139,.1)", borderRadius: 6 }}>{enhancedPrompt}</div>}

          <label>Model</label>
          {modelPicker()}
          <div className="meta"><strong>{currentModel.name}</strong> · {currentModel.desc}</div>

          {type !== "Music" && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <div>
                <label>Aspect Ratio</label>
                <select value={aspect} onChange={function (e) { setAspect(e.target.value); }}>
                  {ASPECTS.map(function (a) { return <option key={a} value={a}>{a}</option>; })}
                </select>
              </div>
              <div>
                <label>Style</label>
                <select value={style} onChange={function (e) { setStyle(e.target.value); }}>
                  {STYLES.map(function (s) { return <option key={s} value={s}>{s}</option>; })}
                </select>
              </div>
            </div>
          )}

          {type === "Image" && sub === "Create" && (
            <div>
              <label>Reference images ({refs.length}/4)</label>
              <div className="refs">
                {[0, 1, 2, 3].map(function (i) {
                  var filled = !!refs[i];
                  return (
                    <div key={i} className="refSlot" onClick={function () { if (!filled) addRef(); }} title={filled ? refs[i] : "上传参考图"}>
                      {filled ? "✓ " + refs[i].slice(-8) : "+ 上传"}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          <div className="meta" style={{ marginTop: 12 }}>
            预估消耗 <strong>{currentModel.credits} credits</strong> · 实际按用量扣
          </div>

          <button className="generate" onClick={generate} disabled={busy || !prompt.trim()}>
            {busy ? "生成中..." : "Generate"}
          </button>
        </div>

        <div className="panel">
          <h3>历史记录 ({history.length})</h3>
          {history.length === 0 ? <p className="meta">还没有生成记录</p> : (
            <div className="history">
              {history.map(function (h) { return (
                <div key={h.id} className="historyItem">
                  <div className="thumb">{h.type === "Image" ? "🖼️" : h.type === "Video" ? "🎞️" : "🎵"}</div>
                  <div className="info">
                    <strong>{h.model}</strong>
                    <small style={{ display: "block", marginTop: 2 }}>{h.prompt.slice(0, 80)}{h.prompt.length > 80 ? "..." : ""}</small>
                    <small>{h.ts} · {h.credits} credits</small>
                  </div>
                </div>
              ); })}
            </div>
          )}
        </div>
      </div>

      <Footer />
    </main>
  );
}

export default PlaygroundPage;
