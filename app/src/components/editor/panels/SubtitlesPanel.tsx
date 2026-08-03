import { useState } from "react";

type PresetShape = SubtitlesPreset & { sample: string };
const PRESETS: PresetShape[] = [
  { id: "classic", name: "经典白底黑字", sample: "你好世界", bg: "#fff", color: "#1a1a1a", fontSize: 28, fontWeight: 700, position: "bottom" },
  { id: "tiktok", name: "TikTok 黄色高亮", sample: "AI 让一切更简单", bg: "transparent", color: "#fff", fontSize: 32, fontWeight: 800, highlight: "#ffe14a", position: "middle" },
  { id: "minimal", name: "极简无背景", sample: "Less is more", bg: "transparent", color: "#fff", fontSize: 24, fontWeight: 500, position: "bottom" },
  { id: "boxed", name: "黑底白字", sample: "Critical point", bg: "#000", color: "#fff", fontSize: 26, fontWeight: 700, position: "bottom" },
  { id: "news", name: "新闻字幕条", sample: "Breaking news", bg: "#cc0000", color: "#fff", fontSize: 26, fontWeight: 800, position: "top" },
  { id: "outline", name: "描边大字", sample: "BOLD TITLE", bg: "transparent", color: "#fff", fontSize: 36, fontWeight: 900, outline: "#000", position: "middle" },
];

export type SubtitlesPreset = {
  id: string;
  name: string;
  bg: string;
  color: string;
  fontSize: number;
  fontWeight: number;
  highlight?: string;
  outline?: string;
  position: "top" | "middle" | "bottom";
};

export type SubtitlesPanelProps = { onPick?: (preset: SubtitlesPreset) => void; activeId?: string };

export function SubtitlesPanel(props: SubtitlesPanelProps) {
  var _a = useState<string>(props.activeId || "tiktok"), selected = _a[0], setSelected = _a[1];
  function pick(p: SubtitlesPreset) {
    setSelected(p.id);
    if (props.onPick) props.onPick(p);
  }
  return (
    <div className="panel">
      <div className="panelHead"><span className="eyebrow">SUBTITLES</span><h3>字幕样式</h3></div>
      <div className="panelSubGrid">
        {PRESETS.map(function (p) {
          var isActive = selected === p.id;
          var preview: React.CSSProperties = {
            background: p.bg,
            color: p.color,
            fontSize: (p.fontSize / 1.5) + "px",
            fontWeight: p.fontWeight,
            textShadow: p.outline ? "-1px -1px 0 " + p.outline + ", 1px -1px 0 " + p.outline + ", -1px 1px 0 " + p.outline + ", 1px 1px 0 " + p.outline : undefined,
            padding: p.bg === "transparent" ? 0 : "8px 14px",
            borderRadius: 6,
            textAlign: "center",
            maxWidth: "100%",
          };
          return (
            <button key={p.id} className={"subPreset" + (isActive ? " active" : "")} onClick={function () { pick(p); }}>
              <div className={"subPreview subPos-" + p.position}><span style={preview}>{p.sample}</span></div>
              <div className="subName">{p.name}</div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default SubtitlesPanel;
