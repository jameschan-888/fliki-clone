import { useState } from "react";
import {
  editorActions,
  editorStore,
  useEditorState,
  type EditorState,
} from "../editorStore";
import { CanvasOverlay } from "../CanvasOverlay";

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
  const currentCharacter = useEditorState((s: EditorState) => s.character);
  const styles = ["全部", "商务", "教育", "科技", "新闻", "生活", "社交"];
  const visibleCharacters = filter === "全部"
    ? CHARACTERS
    : CHARACTERS.filter((c) => c.style === filter);

  function select(c: any) {
    editorActions.selectCharacter({
      id: c.id,
      name: c.name,
      style: c.style,
      region: c.region,
      start_seconds: 0,
    });
  }

  const active = currentCharacter
    ? CHARACTERS.find((c: any) => c.id === currentCharacter.id)
    : null;

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
            className={"characterCardMini" + (currentCharacter && currentCharacter.id === c.id ? " selected" : "")}
            onClick={() => select(c)}
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
              onClick={() => {
                if (currentCharacter) editorActions.setSelectedScene(currentCharacter.id);
              }}
            >
              30s 样音训练 (stub)
            </button>
            <button className="secondary" onClick={() => window.location.href = "/characters.html"}>
              查看完整库
            </button>
            <button className="secondary" onClick={() => editorActions.clearCharacter()}>
              清除
            </button>
          </div>
          <small style={{ display: "block", marginTop: 8, color: "#48d58b", fontSize: 10 }}>
            ✓ 已写入共享 store, Timeline Avatar 轨道可见
          </small>
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
  // P2 drag-resize: 像素级 width/height/x/y, 直接镜像到 Timeline Elements mirror track
  const [width, setWidth] = useState(200);
  const [height, setHeight] = useState(200);
  const [x, setX] = useState(540);
  const [y, setY] = useState(260);
  const elements = useEditorState((s: any) => s.elements);
  const [selectedElId, setSelectedElId] = useState<string | null>(null);
  const selectedEl = elements.find((e: any) => e.id === selectedElId) || null;

  const active = ELEMENT_TYPES.find((e) => e.id === selected);

  function addToScene() {
    if (!active) return;
    editorActions.addElement({
      id: active.id + "-" + Date.now().toString(36),
      position: position as any,
      size,
      opacity,
      width,
      height,
      x,
      y,
    });
  }

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
          <label className="inspectorRow" data-testid="element-width-row">
            <span>宽度 (px)</span>
            <input type="number" min={20} max={1280} value={width} onChange={(ev) => setWidth(Number(ev.target.value) || 0)} />
          </label>
          <label className="inspectorRow" data-testid="element-height-row">
            <span>高度 (px)</span>
            <input type="number" min={20} max={720} value={height} onChange={(ev) => setHeight(Number(ev.target.value) || 0)} />
          </label>
          <label className="inspectorRow" data-testid="element-x-row">
            <span>X 偏移 (px)</span>
            <input type="number" min={0} max={1280} value={x} onChange={(ev) => setX(Number(ev.target.value) || 0)} />
          </label>
          <label className="inspectorRow" data-testid="element-y-row">
            <span>Y 偏移 (px)</span>
            <input type="number" min={0} max={720} value={y} onChange={(ev) => setY(Number(ev.target.value) || 0)} />
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
          <p className="hint">拖入场景或按 + 加入时间轴 (Elements 轨道)。</p>
          <button className="primary" onClick={addToScene}>+ 加入当前场景</button>
        </section>
      )}

      <section className="elementInspector" style={{ marginTop: 12 }}>
        <h4>已添加 ({elements.length})</h4>
        {elements.length === 0 ? (
          <p className="hint">还未添加任何装饰元素。点击上方配置后按 + 加入场景。</p>
        ) : (
          <>
            {elements.map((el: any) => (
              <div
                key={el.id}
                data-testid={"element-row-" + el.id}
                onClick={() => setSelectedElId(el.id)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "6px 0",
                  borderTop: "1px solid #2d3756",
                  cursor: "pointer",
                  background: selectedElId === el.id ? "rgba(25,181,197,0.12)" : "transparent",
                }}
              >
                <span style={{ flex: 1, fontSize: 11, color: "#cfd5ee" }}>{el.id}</span>
                <small style={{ fontSize: 10, color: "#9da8c5" }}>{Math.round(el.width)}x{Math.round(el.height)} @ ({Math.round(el.x)},{Math.round(el.y)})</small>
                <button className="layerBtn danger" title="删除" onClick={(e) => { e.stopPropagation(); editorActions.removeElement(el.id); setSelectedElId(null); }}>✕</button>
              </div>
            ))}
            {selectedEl && (
              <div data-testid="canvas-overlay-mount" style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 6 }}>
                <div style={{ fontSize: 11, color: "#cfd5ee", display: "flex", justifyContent: "space-between" }}>
                  <span>拖动调整 {selectedEl.id}</span>
                  <button className="layerBtn" onClick={() => setSelectedElId(null)} title="关闭预览">✕</button>
                </div>
                <CanvasOverlay
                  element={selectedEl}
                  scale={0.25}
                  onChange={(geom) => editorActions.setElementGeometry(selectedEl.id, geom)}
                />
                <p className="hint">中心拖动改 x/y · 角点拖动改 width/height · 释放后写回 store 与 Timeline</p>
              </div>
            )}
          </>
        )}
      </section>
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

  const fmt = (s: any) =>
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

export function LayersPanel() {
  const layers = useEditorState((s: any) => s.layers);
  const sceneId = useEditorState((s: any) => s.selected_scene_id);

  function move(id: string, target: string) {
    editorActions.reorderLayers(id, target);
  }

  return (
    <div className="panel">
      <div className="panelHead">
        <span className="eyebrow">LAYERS</span>
        <h3>图层 ({layers.length})</h3>
      </div>
      <p className="hint">拖拽 ↕ 改顺序 · 👁 显隐 · 🔒 锁定 · 滑块调不透明度。所有改动同步到 Timeline Layers 轨道。</p>
      <div className="layerList">
        {layers.map((l: any) => (
          <div
            key={l.id}
            className={
              "layerRow" +
              (l.locked ? " locked" : "") +
              (!l.visible ? " hidden" : "")
            }
            draggable={!l.locked}
            onDragStart={(ev) => ev.dataTransfer.setData("text/plain", l.id)}
            onDragOver={(ev) => ev.preventDefault()}
            onDrop={(ev) => {
              const src = ev.dataTransfer.getData("text/plain");
              if (src) move(src, l.id);
            }}
            onClick={() => editorActions.setSelectedScene(l.id)}
          >
            <div className="layerThumb" style={{ background: (editorStore as any).kindColor[l.kind] }}>
              <span>{(editorStore as any).kindIcon[l.kind]}</span>
            </div>
            <div className="layerInfo">
              <strong>{l.name}</strong>
              <small>{l.kind} · {l.opacity}% · {l.visible ? "可见" : "隐藏"}</small>
            </div>
            <div className="layerActions">
              <button title="显隐" onClick={(ev) => { ev.stopPropagation(); editorActions.toggleLayer(l.id); }} className="layerBtn">
                {l.visible ? "👁" : "○"}
              </button>
              <button title="锁定" onClick={(ev) => { ev.stopPropagation(); editorActions.lockLayer(l.id); }} className="layerBtn">
                {l.locked ? "🔒" : "🔓"}
              </button>
              <button title="删除" onClick={(ev) => { ev.stopPropagation(); editorActions.removeLayer(l.id); }} className="layerBtn danger">
                ✕
              </button>
            </div>
            <input
              type="range"
              min={0}
              max={100}
              value={l.opacity}
              className="layerOpacity"
              onClick={(ev) => ev.stopPropagation()}
              onChange={(ev) => editorActions.setLayerOpacity(l.id, Number(ev.target.value))}
              disabled={l.locked}
            />
          </div>
        ))}
      </div>
      <button className="secondary" onClick={() => editorActions.addLayer()}>+ 添加图层</button>
      <div className="layerQuickRow">
        <button onClick={() => editorActions.setLayerVisibilityAll(true)}>全部显示</button>
        <button onClick={() => editorActions.setLayerVisibilityAll(false)}>全部隐藏</button>
        <button onClick={() => editorActions.flipLayers()}>上下翻转</button>
      </div>
      {sceneId && (
        <small style={{ display: "block", marginTop: 8, color: "#48d58b", fontSize: 10 }}>
          当前选中: {sceneId}
        </small>
      )}
    </div>
  );
}
