import { useState } from "react";

const FONTS = ["Noto Sans SC", "Noto Sans", "Inter", "Roboto", "PingFang SC", "Microsoft YaHei"];
const PRESET_PALETTES = [
  { name: "Fliki Default", colors: ["#5b6cff", "#48d58b", "#ffaa28", "#dc5050"] },
  { name: "Ocean", colors: ["#0077b6", "#00b4d8", "#90e0ef", "#caf0f8"] },
  { name: "Sunset", colors: ["#ff8500", "#ffb700", "#ffd60a", "#ff477e"] },
  { name: "Corporate", colors: ["#1a1a2e", "#16213e", "#0f3460", "#533483"] },
  { name: "Forest", colors: ["#2d6a4f", "#40916c", "#52b788", "#95d5b2"] },
];

export type BrandKit = {
  name: string;
  palette: string[];
  font: string;
  logo_data_url: string | null;
  watermark: boolean;
};

export type BrandKitPanelProps = { initial?: Partial<BrandKit>; onChange?: (k: BrandKit) => void };

export function BrandKitPanel(props: BrandKitPanelProps) {
  var _a = useState<BrandKit>({
    name: props.initial?.name || "Default Brand",
    palette: props.initial?.palette || ["#5b6cff", "#48d58b", "#ffaa28", "#dc5050"],
    font: props.initial?.font || "Noto Sans SC",
    logo_data_url: props.initial?.logo_data_url || null,
    watermark: props.initial?.watermark || false,
  }), kit = _a[0], setKit = _a[1];
  function update(patch: Partial<BrandKit>) {
    var next = Object.assign({}, kit, patch);
    setKit(next);
    if (props.onChange) props.onChange(next);
  }
  function setColor(i: number, c: string) {
    var p = kit.palette.slice();
    p[i] = c;
    update({ palette: p });
  }
  function pickPalette(p: typeof PRESET_PALETTES[number]) {
    update({ palette: p.colors.slice(), name: p.name });
  }
  function uploadLogo(file: File) {
    var reader = new FileReader();
    reader.onload = function () { update({ logo_data_url: String(reader.result) }); };
    reader.readAsDataURL(file);
  }
  return (
    <div className="panel">
      <div className="panelHead"><span className="eyebrow">BRAND KIT</span><h3>品牌包</h3></div>

      <label>品牌名</label>
      <input type="text" value={kit.name} onChange={function (e) { update({ name: e.target.value }); }} placeholder="Default Brand" />

      <label>预设色板</label>
      <div className="palettePresets">
        {PRESET_PALETTES.map(function (p) { return (
          <button key={p.name} className={"paletteBtn" + (kit.name === p.name ? " active" : "")} onClick={function () { pickPalette(p); }} title={p.name}>
            {p.colors.map(function (c, i) { return <span key={i} className="paletteSwatch" style={{ background: c }} />; })}
            <small>{p.name}</small>
          </button>
        ); })}
      </div>

      <label>自定义 4 色</label>
      <div className="colorRow">
        {[0, 1, 2, 3].map(function (i) { return (
          <input key={i} type="color" value={kit.palette[i]} onChange={function (e) { setColor(i, e.target.value); }} className="colorInput" />
        ); })}
      </div>

      <label>字体</label>
      <select value={kit.font} onChange={function (e) { update({ font: e.target.value }); }}>
        {FONTS.map(function (f) { return <option key={f} value={f}>{f}</option>; })}
      </select>

      <label>Logo</label>
      <div className="logoRow">
        {kit.logo_data_url ? (
          <div className="logoPreview">
            <img src={kit.logo_data_url} alt="logo" />
            <button onClick={function () { update({ logo_data_url: null }); }}>移除</button>
          </div>
        ) : (
          <label className="logoUpload">
            <input type="file" accept="image/*" onChange={function (e) { var f = e.target.files && e.target.files[0]; if (f) uploadLogo(f); }} hidden />
            <span>+ 上传 Logo (PNG/SVG)</span>
          </label>
        )}
      </div>

      <label className="checkboxLabel">
        <input type="checkbox" checked={kit.watermark} onChange={function (e) { update({ watermark: e.target.checked }); }} />
        启用水印保护
      </label>
    </div>
  );
}

export default BrandKitPanel;
