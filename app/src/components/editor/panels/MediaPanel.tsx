import { useEffect, useState } from "react";

const TABS = ["Stock", "Library", "Generate", "Favorites"] as const;
type Tab = typeof TABS[number];

type Asset = {
  id: string;
  kind: "image" | "video" | "gif";
  title: string;
  meta?: string;
  source: "stock" | "library" | "generated";
};

function placeholderAssets(tab: Tab, query: string): Asset[] {
  var data: Asset[] = [];
  if (tab === "Stock") {
    data = [
      { id: "s1", kind: "image", title: "城市夜景", meta: "pexels · 4K", source: "stock" },
      { id: "s2", kind: "video", title: "森林 4K B-roll", meta: "pexels · 10s", source: "stock" },
      { id: "s3", kind: "image", title: "桌面办公", meta: "pixabay · free", source: "stock" },
      { id: "s4", kind: "video", title: "咖啡冲泡", meta: "pexels · 8s", source: "stock" },
      { id: "s5", kind: "image", title: "数据图表", meta: "pixabay · free", source: "stock" },
      { id: "s6", kind: "gif", title: "动效素材", meta: "giphy", source: "stock" },
    ];
  } else if (tab === "Library") {
    data = [
      { id: "l1", kind: "image", title: "我的上传图 1", meta: "2026-08-01", source: "library" },
      { id: "l2", kind: "video", title: "我的上传视频", meta: "15s", source: "library" },
    ];
  } else if (tab === "Generate") {
    data = [
      { id: "g1", kind: "image", title: "Veo 3.1 生成", meta: "0.05 credits", source: "generated" },
      { id: "g2", kind: "image", title: "Sora 2 生成", meta: "0.10 credits", source: "generated" },
      { id: "g3", kind: "image", title: "Kling 3 Pro", meta: "0.08 credits", source: "generated" },
    ];
  } else {
    data = [{ id: "f1", kind: "image", title: "收藏 1", source: "library" }];
  }
  return data.filter(function (a) { return !query || a.title.toLowerCase().indexOf(query.toLowerCase()) !== -1; });
}

export type MediaPanelProps = { onPick?: (asset: Asset) => void };

export function MediaPanel(props: MediaPanelProps) {
  var _a = useState<Tab>("Stock"), tab = _a[0], setTab = _a[1];
  var _b = useState(""), q = _b[0], setQ = _b[1];
  var _c = useState<Asset[]>([]), items = _c[0], setItems = _c[1];
  useEffect(function () { setItems(placeholderAssets(tab, q)); }, [tab, q]);
  function pick(a: Asset) { if (props.onPick) props.onPick(a); }
  return (
    <div className="panel">
      <div className="panelHead"><span className="eyebrow">MEDIA</span><h3>素材库</h3></div>
      <div className="panelTabs">
        {TABS.map(function (t) { return (
          <button key={t} className={"panelTab" + (tab === t ? " active" : "")} onClick={function () { setTab(t); }}>{t}</button>
        ); })}
      </div>
      <input
        className="panelSearch"
        type="search"
        placeholder="搜索 城市, 森林, 咖啡..."
        value={q}
        onChange={function (e) { setQ(e.target.value); }}
      />
      <div className="panelGrid">
        {items.length === 0 ? <p className="panelEmpty">没有匹配素材</p> : items.map(function (a) {
          return (
            <button key={a.id} className={"asset asset-" + a.kind} onClick={function () { pick(a); }} title={a.title + " · " + (a.meta || "")}>
              <span className="assetIcon">{a.kind === "image" ? "🖼️" : a.kind === "video" ? "🎞️" : "✨"}</span>
              <span className="assetTitle">{a.title}</span>
              {a.meta && <small>{a.meta}</small>}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default MediaPanel;
