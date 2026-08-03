import { useEffect, useState } from "react";

export type TemplatesPanelProps = {
  onPick?: (template: { id: string; name: string; category?: string; aspect_ratio?: string }) => void;
};

type Tpl = { id: string; name: string; category?: string; aspect_ratio?: string; description?: string };

export function TemplatesPanel(props: TemplatesPanelProps) {
  var _a = useState<Tpl[]>([]), items = _a[0], setItems = _a[1];
  var _b = useState(""), q = _b[0], setQ = _b[1];
  var _c = useState<string>(""), cat = _c[0], setCat = _c[1];
  useEffect(function () {
    fetch("/templates", { headers: { Authorization: "Bearer " + (localStorage.getItem("fliki-auth-token") || "") } })
      .then(function (r) { return r.ok ? r.json() : []; })
      .then(function (arr) { setItems(Array.isArray(arr) ? arr : []); })
      .catch(function () { setItems([]); });
  }, []);
  var cats = Array.from(new Set(items.map(function (t) { return t.category || ""; }).filter(Boolean)));
  var filtered = items.filter(function (t) {
    if (cat && t.category !== cat) return false;
    if (q && t.name.toLowerCase().indexOf(q.toLowerCase()) === -1) return false;
    return true;
  });
  return (
    <div className="panel">
      <div className="panelHead"><span className="eyebrow">TEMPLATES</span><h3>场景模板</h3></div>
      <div className="panelCats">
        <button className={"panelCat" + (!cat ? " active" : "")} onClick={function () { setCat(""); }}>全部</button>
        {cats.map(function (c) { return (
          <button key={c} className={"panelCat" + (cat === c ? " active" : "")} onClick={function () { setCat(c); }}>{c}</button>
        ); })}
      </div>
      <input
        className="panelSearch"
        type="search"
        placeholder="搜索模板..."
        value={q}
        onChange={function (e) { setQ(e.target.value); }}
      />
      <div className="panelList">
        {filtered.length === 0 ? <p className="panelEmpty">没有模板</p> : filtered.map(function (t) {
          return (
            <button key={t.id} className="tplItem" onClick={function () { if (props.onPick) props.onPick(t); }}>
              <span className="tplIcon">🧩</span>
              <span className="tplMain"><strong>{t.name}</strong>{t.description && <small>{t.description}</small>}</span>
              <span className="tplMeta">{t.category || ""}{t.aspect_ratio ? " · " + t.aspect_ratio : ""}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default TemplatesPanel;
