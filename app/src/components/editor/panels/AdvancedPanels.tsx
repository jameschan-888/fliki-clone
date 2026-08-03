import { useState } from "react";

export function CopilotPanel() {
  const [prompt, setPrompt] = useState("");
  const [messages, setMessages] = useState<string[]>([]);
  function apply() { if (!prompt.trim()) return; setMessages((items) => items.concat("你: " + prompt, "Copilot: 已生成编辑建议，可应用到当前场景")); setPrompt(""); }
  return <div className="panel"><div className="panelHead"><span className="eyebrow">COPILOT</span><h3>AI 助手</h3></div><div className="copilotMessages">{messages.length ? messages.map((item, index) => <p key={index}>{item}</p>) : <p className="hint">试试“让这一场更适合 TikTok”或“缩短旁白”。</p>}</div><textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="告诉 Copilot 你想怎么改..." rows={4} /><button className="primary" onClick={apply}>发送指令</button></div>;
}

const characters = ["Alex · 商务", "Mia · 教育", "Jordan · 科技", "Sofia · 新闻", "Taylor · 生活方式", "Emma · 社交"];
export function CharacterPanel() { const [filter, setFilter] = useState("全部"); return <div className="panel"><div className="panelHead"><span className="eyebrow">CHARACTER</span><h3>角色</h3></div><select value={filter} onChange={(event) => setFilter(event.target.value)}><option>全部</option><option>商务</option><option>教育</option><option>科技</option></select><div className="characterMiniGrid">{characters.filter((item) => filter === "全部" || item.includes(filter)).map((item) => <button key={item} onClick={() => setFilter(item.split(" · ")[1])}><span className="miniAvatar">{item[0]}</span>{item}</button>)}</div><button className="secondary" onClick={() => window.location.href = "/characters.html"}>打开完整角色库</button></div>; }

const elements = ["形状", "贴纸", "图标", "进度条", "箭头", "CTA 按钮", "高亮框", "装饰线"];
export function ElementsPanel() { const [selected, setSelected] = useState(""); return <div className="panel"><div className="panelHead"><span className="eyebrow">ELEMENTS</span><h3>装饰元素</h3></div><div className="elementGrid">{elements.map((item) => <button className={selected === item ? "active" : ""} key={item} onClick={() => setSelected(item)}>{item}</button>)}</div>{selected && <p className="hint">已选择：{selected}，可拖入当前场景。</p>}</div>; }

export function RecordPanel() { const [recording, setRecording] = useState(false); const [mode, setMode] = useState("Screen + Mic"); return <div className="panel"><div className="panelHead"><span className="eyebrow">RECORD</span><h3>录制</h3></div><select value={mode} onChange={(event) => setMode(event.target.value)}><option>Screen + Mic</option><option>Webcam + Mic</option><option>Microphone only</option></select><button className={recording ? "danger" : "primary"} onClick={() => setRecording(!recording)}>{recording ? "停止录制" : "开始录制"}</button><p className="hint">{recording ? "正在采集媒体，停止后可生成 transcript。" : "录制内容会进入 Record to Video 工作流。"}</p></div>; }

export function LayersPanel() { const [layers, setLayers] = useState(["背景", "字幕", "旁白"]); return <div className="panel"><div className="panelHead"><span className="eyebrow">LAYERS</span><h3>图层</h3></div><div className="layerList">{layers.map((item, index) => <div key={item}><button onClick={() => setLayers((items) => items.filter((layer) => layer !== item))}>×</button><span>{index + 1}. {item}</span><small>可见</small></div>)}</div><button className="secondary" onClick={() => setLayers((items) => items.concat("新图层 " + (items.length + 1)))}>+ 添加图层</button></div>; }
