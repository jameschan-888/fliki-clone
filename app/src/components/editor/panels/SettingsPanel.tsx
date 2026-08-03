import { useState } from "react";

const ASPECTS = [
  { id: "9:16", label: "9:16", desc: "TikTok / Reels / Shorts" },
  { id: "1:1", label: "1:1", desc: "Instagram / Square" },
  { id: "16:9", label: "16:9", desc: "YouTube / 横屏" },
  { id: "4:5", label: "4:5", desc: "Instagram Portrait" },
] as const;

const FONTS = ["Noto Sans SC", "Noto Sans", "Inter", "Roboto", "PingFang SC", "Microsoft YaHei"];

const COLORS = ["#5b6cff", "#48d58b", "#dc5050", "#ffaa28", "#aa44ff", "#1a1a2e"];

export type Settings = {
  aspect: string;
  scene_gap: number;
  brand_kit: string | null;
  background: string;
  font: string;
  primary_color: string;
};

export type SettingsPanelProps = {
  initial?: Partial<Settings>;
  onChange?: (s: Settings) => void;
};

export function SettingsPanel(props: SettingsPanelProps) {
  var _a = useState<Settings>({
    aspect: props.initial?.aspect || "16:9",
    scene_gap: props.initial?.scene_gap || 0,
    brand_kit: props.initial?.brand_kit || null,
    background: props.initial?.background || "#0c1020",
    font: props.initial?.font || "Noto Sans SC",
    primary_color: props.initial?.primary_color || "#5b6cff",
  }), settings = _a[0], setSettings = _a[1];
  function update(patch: Partial<Settings>) {
    var next = Object.assign({}, settings, patch);
    setSettings(next);
    if (props.onChange) props.onChange(next);
  }
  return (
    <div className="panel">
      <div className="panelHead"><span className="eyebrow">SETTINGS</span><h3>项目设置</h3></div>

      <div className="settingsGroup">
        <label className="settingsLabel">ASPECT_RATIO</label>
        <div className="aspectGrid">
          {ASPECTS.map(function (a) { return (
            <button key={a.id} className={"aspectBtn" + (settings.aspect === a.id ? " active" : "")} onClick={function () { update({ aspect: a.id }); }} title={a.desc}>
              <strong>{a.label}</strong><small>{a.desc}</small>
            </button>
          ); })}
        </div>
      </div>

      <div className="settingsGroup">
        <label className="settingsLabel">SCENE GAP (秒)</label>
        <input type="number" min={0} max={5} step={0.5} value={settings.scene_gap} onChange={function (e) { update({ scene_gap: Number(e.target.value) || 0 }); }} className="settingsInput" />
      </div>

      <div className="settingsGroup">
        <label className="settingsLabel">BRAND KIT</label>
        <div className="brandRow">
          {settings.brand_kit ? (
            <span className="brandOn">已绑定: {settings.brand_kit}</span>
          ) : (
            <button className="brandLink" onClick={function () { update({ brand_kit: "default" }); }}>+ 链接 Brand Kit</button>
          )}
        </div>
      </div>

      <div className="settingsGroup">
        <label className="settingsLabel">BACKGROUND</label>
        <div className="colorRow">
          {COLORS.map(function (c) { return (
            <button key={c} className={"colorSwatch" + (settings.background === c ? " active" : "")} style={{ background: c }} onClick={function () { update({ background: c }); }} title={c} />
          ); })}
        </div>
      </div>

      <div className="settingsGroup">
        <label className="settingsLabel">FONT</label>
        <select className="settingsInput" value={settings.font} onChange={function (e) { update({ font: e.target.value }); }}>
          {FONTS.map(function (f) { return <option key={f} value={f}>{f}</option>; })}
        </select>
      </div>

      <div className="settingsGroup">
        <label className="settingsLabel">PRIMARY COLOR</label>
        <div className="colorRow">
          {COLORS.map(function (c) { return (
            <button key={c} className={"colorSwatch" + (settings.primary_color === c ? " active" : "")} style={{ background: c }} onClick={function () { update({ primary_color: c }); }} title={c} />
          ); })}
        </div>
      </div>
    </div>
  );
}

export default SettingsPanel;
