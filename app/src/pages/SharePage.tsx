import { useEffect, useState } from "react";
import { API } from "../api/drafts";

type Scene = { title: string; narration: string; subtitle?: string; duration_seconds?: number };
export function SharePage() {
  const [title, setTitle] = useState("分享预览");
  const [scenes, setScenes] = useState<Scene[]>([]);
  const [error, setError] = useState("");
  useEffect(() => { const token = new URLSearchParams(window.location.search).get("token") || window.location.pathname.split("/").filter(Boolean).pop() || ""; void fetch(API + "/share/" + encodeURIComponent(token)).then(async (response) => { const body = await response.json(); if (!response.ok) throw new Error(body.detail?.message || "分享链接无效或已撤销"); const draft = body.share.draft; setTitle(draft.title || "分享预览"); setScenes(draft.scenes || []); }).catch((loadError) => setError(loadError instanceof Error ? loadError.message : "加载失败")); }, []);
  if (error) return <main className="sharePage"><div className="shareError" role="alert"><h1>无法打开分享</h1><p>{error}</p><a href="/index.html">返回首页</a></div></main>;
  return <main className="sharePage"><header className="shareHeader"><a href="/index.html">Fliki Studio</a><span>只读预览</span></header><section className="shareHero"><span className="eyebrow">SHARED VIDEO</span><h1>{title}</h1><p>由 Fliki Studio 创建 · 可查看脚本与场景结构</p></section><section className="shareScenes">{scenes.map((scene, index) => <article className="shareScene" key={index}><div className="shareSceneNumber">{String(index + 1).padStart(2, "0")}</div><div><h2>{scene.title || "场景 " + (index + 1)}</h2><p>{scene.narration || scene.subtitle}</p><small>{scene.duration_seconds || 4}s</small></div></article>)}</section><footer className="shareFooter"><a href="/drafts.html">用 Fliki 创建你的视频 →</a></footer></main>;
}
