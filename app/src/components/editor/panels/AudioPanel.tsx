import { useEffect, useState } from "react";

const CATS = ["Music", "SFX", "YouTube"] as const;
const TABS = ["Stock", "Library", "Generate", "Favorites"] as const;

type AudioSource = "stock" | "library" | "generated";
type AudioItem = {
  id: string;
  title: string;
  duration: string;
  genre: string;
  source: AudioSource;
};

function placeholderAudio(cat: string, q: string): AudioItem[] {
  var data: AudioItem[];
  if (cat === "Music") {
    data = [
      { id: "m1", title: "Futuristic Spell", duration: "00:02", genre: "Scifi", source: "stock" },
      { id: "m2", title: "Futuristic Avalanche", duration: "00:27", genre: "Scifi", source: "stock" },
      { id: "m3", title: "Futuristic Cosmic Lava", duration: "00:12", genre: "Scifi", source: "stock" },
      { id: "m4", title: "Sci Lab Experiment", duration: "01:27", genre: "Scifi", source: "stock" },
      { id: "m5", title: "Lo-fi Beats", duration: "02:30", genre: "Lo-fi", source: "stock" },
    ];
  } else if (cat === "SFX") {
    data = [
      { id: "s1", title: "UI Click", duration: "00:01", genre: "UI", source: "stock" },
      { id: "s2", title: "Cartoon Pop", duration: "00:01", genre: "Cartoon", source: "stock" },
      { id: "s3", title: "Alarm Beep", duration: "00:02", genre: "Alarms", source: "stock" },
    ];
  } else {
    data = [{ id: "y1", title: "YouTube Music - Trending 1", duration: "03:24", genre: "Pop", source: "library" }];
  }
  return data.filter(function (a) { return !q || a.title.toLowerCase().indexOf(q.toLowerCase()) !== -1; });
}

export type AudioPanelProps = { onPick?: (item: AudioItem) => void };

export function AudioPanel(props: AudioPanelProps) {
  var _a = useState<string>("Stock"), tab = _a[0], setTab = _a[1];
  var _b = useState<string>("Music"), cat = _b[0], setCat = _b[1];
  var _c = useState(""), q = _c[0], setQ = _c[1];
  var _d = useState<AudioItem[]>([]), items = _d[0], setItems = _d[1];
  useEffect(function () { setItems(placeholderAudio(cat, q)); }, [cat, q]);
  function pick(a: AudioItem) { if (props.onPick) props.onPick(a); }
  return (
    <div className="panel">
      <div className="panelHead"><span className="eyebrow">AUDIO</span><h3>音频</h3></div>
      <div className="panelTabs">
        {TABS.map(function (t) { return (
          <button key={t} className={"panelTab" + (tab === t ? " active" : "")} onClick={function () { setTab(t); }}>{t}</button>
        ); })}
      </div>
      <div className="panelCats">
        {CATS.map(function (c) { return (
          <button key={c} className={"panelCat" + (cat === c ? " active" : "")} onClick={function () { setCat(c); }}>{c}</button>
        ); })}
      </div>
      <input
        className="panelSearch"
        type="search"
        placeholder="搜索 groovy, beat, happy..."
        value={q}
        onChange={function (e) { setQ(e.target.value); }}
      />
      <div className="panelList">
        {items.length === 0 ? <p className="panelEmpty">没有匹配</p> : items.map(function (a) {
          return (
            <button key={a.id} className="audioItem" onClick={function () { pick(a); }}>
              <span className="audioPlay">▶</span>
              <span className="audioTitle">{a.title}</span>
              <span className="audioMeta">{a.duration} · {a.genre}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default AudioPanel;
