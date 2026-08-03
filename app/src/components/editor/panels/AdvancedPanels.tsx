import { useState } from "react";

export function CopilotPanel() {
  const [prompt, setPrompt] = useState("");
  const [messages, setMessages] = useState<string[]>([]);
  function apply() {
    if (!prompt.trim()) return;
    setMessages((items) =>
      items.concat(
        "你: " + prompt,
        "Copilot: 已生成编辑建议，可应用到当前场景。",
      ),
    );
    setPrompt("");
  }
  return (
    <div className="panel">
      <div className="panelHead">
        <span className="eyebrow">COPILOT</span>
        <h3>AI 助手</h3>
      </div>
      <div className="copilotMessages">
        {messages.length ? (
          messages.map((item, index) => (
            <p key={index}>{item}</p>
          ))
        ) : (
          <p className="hint">试试 "让这一场更适合 TikTok" 或 "缩短旁白"。</p>
        )}
      </div>
      <textarea
        value={prompt}
        onChange={(event) => setPrompt(event.target.value)}
        placeholder="告诉 Copilot 你想怎么改..."
        rows={4}
      />
      <button className="primary" onClick={apply}>
        发送指令
      </button>
    </div>
  );
}

const CHARACTERS = [
  { id: "alex",    name: "Alex",    style: "商务",    region: "US",    tone: "沉稳" },
  { id: "mia",     name: "Mia",     style: "教育",    region: "UK",    tone: "温柔" },
  { id: "jordan",  name: "Jordan",  style: "科技",    region: "CA",    tone: "活力" },
  { id: "sofia",   name: "Sofia",   style: "新闻",    region: "ES",    tone: "清脆" },
  { id: "taylor",  name: "Taylor",  style: "生活",    region: "AU",    tone: "亲和" },
  { id: "emma",    name: "Emma",    style: "社交",    region: "US",    tone: "俏皮" },
  { id: "wei",     name: "Wei",     style: "教育",    region: "CN",    tone: "磁性" },
  { id: "yuki",    name: "Yuki",    style: "科技",    region: "JP",    tone: "安静" },
  { id: "priya",   name: "Priya",   style: "商业",    region: "IN",    tone: "说服" },
  { id: "lucas",   name: "Lucas",   style: "社交",    region: "BR",    tone: "热情" },
  { id: "emma_de", name: "Emma",    style: "新闻",    region: "DE",    tone: "权威" },
  { id: "kenji",   name: "Kenji",   style: "生活",    region: "SG",    tone: "放松" },
];

export function CharacterPanel() {
  const [filter, setFilter] = useState("全部");
  const [selected, setSelected] = useState("");
  const [training, setTraining] = useState(false);
  const [progress, setProgress] = useState(0);

  const styles = ["全部", "商务", "教育", "科技", "新闻", "生活", "社交"];
  const visibleCharacters = filter === "全部"
    ? CHARACTERS
    : CHARACTERS.filter((c) => c.style === filter);

  function startTraining(id: string) {
    setSelected(id);
    setTraining(true);
    setProgress(0);
    const tick = setInterval(() => {
      setProgress((p) => {
        const next = p + 8;
        if (next >= 100) {
          clearInterval(tick);
          setTraining(false);
          return 100;
        }
        return next;
      });
    }, 80);
  }

  const active = CHARACTERS.find((c) => c.id === selected);

  return (
    <div className="panel">
      <div className="panelHead">
        <span className="eyebrow">CHARACTER</span>
        <h3>数字人角色 ({CHARACTERS.length})</h3>
      </div>
      <div className="filterRow" style={{ marginTop: 6 }}>
        {styles.map((s) => (
          <button
            key={s}
            className={filter === s ? "selected" : ""}
            onClick={() => setFilter(s)}
          >
            {s}
          </button>
        ))}
      </div>
      <div className="characterMiniGrid">
        {visibleCharacters.map((c) => (
          <div
            key={c.id}
            className={"characterCardMini" + (selected === c.id ? " selected" : "")}
            onClick={() => setSelected(c.id)}
          >
            <span
              className="miniAvatar"
              style={{
                background: ["#5b6cff","#48d58b","#f5a524","#e85d75","#8a6cff","#19b5c5"][CHARACTERS.indexOf(c) % 6],
              }}
            >
              {c.name[0]}
            </span>
            <div className="characterCardMiniInfo">
              <strong>{c.name}</strong>
              <small>{c.style} · {c.region} · {c.tone}</small>
            </div>
          </div>
        ))}
      </div>
      {active && (
        <section className="characterDetail">
          <div className="characterDetailHead">
            <span className="miniAvatar" style={{ width: 40, height: 40, fontSize: 18 }}>{active.name[0]}</span>
            <div>
              <strong>{active.name} · {active.style}</strong>
              <small>{active.region} · {active.tone} · 12 种语言</small>
            </div>
          </div>
          <div className="characterActions">
            <button
              className="primary"
              onClick={() => startTraining(active.id)}
              disabled={training}
            >
              {training ? "训练中 " + progress + "%" : "训练 30s 样音"}
            </button>
            <button className="secondary" onClick={() => window.location.href = "/characters.html"}>
              查看完整库
            </button>
          </div>
          {training && (
            <progress max={100} value={progress} />
          )}
        </section>
      )}
    </div>
  );
}

const ELEMENT_TYPES = [
  { id: "shape",          label: "形状",          color: "#5b6cff", icon: "◇" },
  { id: "sticker",        label: "贴纸",          color: "#48d58b", icon: "✿" },
  { id: "icon",           label: "图标",          color: "#f5a524", icon: "☆" },
  { id: "bar",            label: "进度条",        color: "#e85d75", icon: "▰" },
  { id: "arrow",          label: "箭头",          color: "#8a6cff", icon: "→" },
  { id: "cta",            label: "CTA",           color: "#19b5c5", icon: "✓" },
  { id: "highlight",      label: "高亮框",        color: "#ffd166", icon: "□" },
  { id: "line",           label: "装饰线",        color: "#ff9aa2", icon: "─" },
  { id: "lower-third",    label: "下三分之一",    color: "#7bd0ff", icon: "❰❱" },
  { id: "bubble",         label: "对话泡",        color: "#a3e635", icon: "◯" },
  { id: "counter",        label: "数字滚屏",      color: "#fb7185", icon: "↑" },
  { id: "background-blur",label: "背景模糊",      color: "#94a3b8", icon: "▢" },
  { id: "lottie",         label: "Lottie 动画",   color: "#22c55e", icon: "❄" },
  { id: "caption",        label: "字幕",          color: "#3b82f6", icon: "T" },
  { id: "logo",           label: "品牌 Logo",     color: "#ec4899", icon: "●" },
  { id: "watermark",      label: "水印",          color: "#0ea5e9", icon: "©" },
];

export function ElementsPanel() {
  const [selected, setSelected] = useState("");
  const [opacity, setOpacity] = useState(100);
  const [size, setSize] = useState(100);
  const [position, setPosition] = useState("bottom-right");

  const active = ELEMENT_TYPES.find((e) => e.id === selected);

  return (
    <div className="panel">
      <div className="panelHead">
        <span className="eyebrow">ELEMENTS</span>
        <h3>装饰元素 ({ELEMENT_TYPES.length})</h3>
      </div>
      <div className="elementGrid">
        {ELEMENT_TYPES.map((e) => (
          <button
            className={selected === e.id ? "active" : ""}
            key={e.id}
            draggable
            onDragStart={(ev) => ev.dataTransfer.setData("text/plain", e.id)}
            onClick={() => setSelected(e.id)}
            title={"拖入场景或点击配置"}
          >
            <span style={{ marginRight: 6, color: e.color }}>{e.icon}</span>{e.label}
          </button>
        ))}
      </div>
      {active && (
        <section className="elementInspector">
          <h4>配置：{active.label}</h4>
          <label className="inspectorRow">
            <span>不透明度</span>
            <input
              type="range"
              min={0}
              max={100}
              value={opacity}
              onChange={(ev) => setOpacity(Number(ev.target.value))}
            />
            <small>{opacity}%</small>
          </label>
          <label className="inspectorRow">
            <span>大小</span>
            <input
              type="range"
              min={20}
              max={300}
              value={size}
              onChange={(ev) => setSize(Number(ev.target.value))}
            />
            <small>{size}%</small>
          </label>
          <label className="inspectorRow">
            <span>位置</span>
            <select value={position} onChange={(ev) => setPosition(ev.target.value)}>
              <option value="top-left">左上</option>
              <option value="top-right">右上</option>
              <option value="bottom-left">左下</option>
              <option value="bottom-right">右下</option>
              <option value="center">居中</option>
            </select>
          </label>
          <div className="elementPreview" style={{ opacity: opacity / 100 }}>
            <span
              style={{
                display: "inline-flex",
                width: 56,
                height: 56,
                fontSize: 28,
                alignItems: "center",
                justifyContent: "center",
                borderRadius: 10,
                background: active.color + "33",
                color: active.color,
                border: "1px solid " + active.color,
                transform: "scale(" + (size / 100) + ")",
                transition: "transform 0.2s",
              }}
            >{active.icon}</span>
          </div>
          <p className="hint">拖入场景或按 + 加入时间轴。</p>
          <button
            className="secondary"
            onClick={() => {
              const ev = new CustomEvent("addElement", { detail: { id: active.id, opacity, size, position } });
              window.dispatchEvent(ev);
            }}
          >
            + 加入当前场景
          </button>
        </section>
      )}
    </div>
  );
}

export function RecordPanel() {
  const [recording, setRecording] = useState(false);
  const [mode, setMode] = useState("Screen + Mic");
  const [seconds, setSeconds] = useState(0);
  const [duration, setDuration] = useState(0);

  function startStop() {
    if (recording) {
      setDuration(seconds);
      setRecording(false);
      setSeconds(0);
      return;
    }
    setRecording(true);
    const tick = setInterval(() => setSeconds((s) => s + 1), 1000);
    setTimeout(() => {
      clearInterval(tick);
      setRecording(false);
      setDuration(seconds);
    }, 60_000);
  }

  const fmt = (s: number) =>
    Math.floor(s / 60).toString().padStart(2, "0") + ":" + (s % 60).toString().padStart(2, "0");

  return (
    <div className="panel">
      <div className="panelHead">
        <span className="eyebrow">RECORD</span>
        <h3>录制</h3>
      </div>
      <select value={mode} onChange={(event) => setMode(event.target.value)}>
        <option>Screen + Mic</option>
        <option>Webcam + Mic</option>
        <option>Microphone only</option>
        <option>Tab + Audio</option>
      </select>
      <button className={recording ? "danger" : "primary"} onClick={startStop}>
        {recording ? "停止录制 (" + fmt(seconds) + ")" : "开始录制"}
      </button>
      <p className="hint">
        {recording
          ? "正在采集媒体，超时或停止后自动转写 transcript。"
          : duration > 0
          ? "上次录制 " + fmt(duration) + "，已进入 Record 草稿。"
          : "录制内容会进入 Record to Video 工作流。"}
      </p>
      <div className="recordMeta">
        <small>· 浏览器 MediaRecorder (webm)</small><br />
        <small>· 自动 ASR (faster-whisper)</small><br />
        <small>· 单段上限 60s, 总时长不限</small>
      </div>
    </div>
  );
}

type Layer = {
  id: string;
  name: string;
  kind: string;
  visible: boolean;
  opacity: number;
  locked: boolean;
};

const DEFAULT_LAYERS: Layer[] = [
  { id: "l1", name: "背景",     kind: "background", visible: true, opacity: 100, locked: false },
  { id: "l2", name: "主视频",   kind: "video",      visible: true, opacity: 100, locked: false },
  { id: "l3", name: "数字人",   kind: "avatar",     visible: true, opacity: 100, locked: false },
  { id: "l4", name: "装饰元素", kind: "element",    visible: true, opacity: 80,  locked: false },
  { id: "l5", name: "字幕",     kind: "subtitle",   visible: true, opacity: 100, locked: false },
  { id: "l6", name: "水印",     kind: "watermark",  visible: true, opacity: 35,  locked: true },
];

const KIND_COLOR: Record<string, string> = {
  background: "#5b6cff",
  video: "#48d58b",
  avatar: "#f5a524",
  element: "#19b5c5",
  subtitle: "#7bd0ff",
  watermark: "#94a3b8",
};

const KIND_ICON: Record<string, string> = {
  background: "▢",
  video: "▶",
  avatar: "◎",
  element: "◇",
  subtitle: "T",
  watermark: "©",
};

export function LayersPanel() {
  const [layers, setLayers] = useState<Layer[]>(DEFAULT_LAYERS);
  const [draggingId, setDraggingId] = useState<string | null>(null);

  function toggle(id: string) {
    setLayers((items) => items.map((l) => (l.id === id ? { ...l, visible: !l.visible } : l)));
  }
  function setOpacity(id: string, opacity: number) {
    setLayers((items) => items.map((l) => (l.id === id ? { ...l, opacity } : l)));
  }
  function lock(id: string) {
    setLayers((items) => items.map((l) => (l.id === id ? { ...l, locked: !l.locked } : l)));
  }
  function remove(id: string) {
    setLayers((items) => items.filter((l) => l.id !== id));
  }
  function add() {
    const next: Layer = {
      id: "l" + (layers.length + 1),
      name: "新图层 " + (layers.length + 1),
      kind: "element",
      visible: true,
      opacity: 100,
      locked: false,
    };
    setLayers((items) => items.concat(next));
  }
  function reorder(srcId: string, targetId: string) {
    if (srcId === targetId) return;
    setLayers((items) => {
      const srcIndex = items.findIndex((l) => l.id === srcId);
      const targetIndex = items.findIndex((l) => l.id === targetId);
      if (srcIndex < 0 || targetIndex < 0) return items;
      const next = items.slice();
      const moved = next.splice(srcIndex, 1)[0];
      next.splice(targetIndex, 0, moved);
      return next;
    });
  }

  return (
    <div className="panel">
      <div className="panelHead">
        <span className="eyebrow">LAYERS</span>
        <h3>图层 ({layers.length})</h3>
      </div>
      <p className="hint">拖拽排序 · 👁 显隐 · 🔒 锁定 · 滑块调节不透明度。</p>
      <div className="layerList">
        {layers.map((l) => (
          <div
            key={l.id}
            className={
              "layerRow" +
              (draggingId === l.id ? " dragging" : "") +
              (l.locked ? " locked" : "") +
              (!l.visible ? " hidden" : "")
            }
            draggable={!l.locked}
            onDragStart={() => setDraggingId(l.id)}
            onDragOver={(ev) => ev.preventDefault()}
            onDrop={() => {
              if (draggingId) reorder(draggingId, l.id);
              setDraggingId(null);
            }}
            onDragEnd={() => setDraggingId(null)}
          >
            <div className="layerThumb" style={{ background: KIND_COLOR[l.kind] || "#5b6cff" }}>
              <span>{KIND_ICON[l.kind] || "◇"}</span>
            </div>
            <div className="layerInfo">
              <strong>{l.name}</strong>
              <small>{l.kind} · {l.opacity}% · {l.visible ? "可见" : "隐藏"}</small>
            </div>
            <div className="layerActions">
              <button title="显隐" onClick={() => toggle(l.id)} className="layerBtn">
                {l.visible ? "👁" : "○"}
              </button>
              <button title="锁定" onClick={() => lock(l.id)} className="layerBtn">
                {l.locked ? "🔒" : "🔓"}
              </button>
              <button title="删除" onClick={() => remove(l.id)} className="layerBtn danger">
                ✕
              </button>
            </div>
            <input
              type="range"
              min={0}
              max={100}
              value={l.opacity}
              className="layerOpacity"
              onChange={(ev) => setOpacity(l.id, Number(ev.target.value))}
              disabled={l.locked}
            />
          </div>
        ))}
      </div>
      <button className="secondary" onClick={add}>+ 添加图层</button>
      <div className="layerQuickRow">
        <button onClick={() => setLayers((items) => items.map((l) => ({ ...l, visible: true })))}>全部显示</button>
        <button onClick={() => setLayers((items) => items.map((l) => ({ ...l, visible: false })))}>全部隐藏</button>
        <button onClick={() => setLayers((items) => [...items].reverse())}>上下翻转</button>
      </div>
    </div>
  );
}
