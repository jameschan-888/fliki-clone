import React from "react";
import { createRoot } from "react-dom/client";
import { Footer } from "./components/layout/Footer";
import "./styles/app.css";

type PlatformInfo = { label: string; handle: string; blurb: string };
const PLATFORM_INFO: Record<string, PlatformInfo> = {
  twitter: { label: "X (Twitter)", handle: "@flikiStudio", blurb: "产品动态 + 团队日常，每日 1-2 条。" },
  youtube: { label: "YouTube", handle: "本地视频制作台", blurb: "新功能演示 + 用户案例视频。" },
  linkedin: { label: "LinkedIn", handle: "Local Video Studio", blurb: "企业故事 + 招聘 + 行业观点。" },
  tiktok: { label: "TikTok", handle: "@flikiStudio", blurb: "30 秒短视频教程 + 灵感。" },
  github: { label: "GitHub", handle: "local-video-studio", blurb: "代码、Issues、Discussions。" },
};

function getPlatform() {
  const path = window.location.pathname.replace(/^\/social\//, "").replace(/\.html$/, "");
  return PLATFORM_INFO[path] ? path : "twitter";
}

function SocialLanding() {
  const p = getPlatform();
  const info = PLATFORM_INFO[p];
  return (
    <main className="catalogPage legalPage">
      <nav className="catalogNav">
        <a href="/index.html">Fliki Studio</a>
        <span>
          <a href="/features.html">Features</a>
          <a href="/pricing.html">Pricing</a>
          <a href="/use-cases.html">Use cases</a>
        </span>
        <a className="catalogButton" href="/drafts.html">免费开始</a>
      </nav>
      <section className="catalogHero legalHero">
        <span className="eyebrow">SOCIAL</span>
        <h1>{info.label}</h1>
        <p>关注 {info.handle}</p>
        <div className="legalMeta">{info.blurb}</div>
      </section>
      <section className="legalBody">
        <section className="legalSection">
          <h2>关注我们</h2>
          <p>本仓库是离线优先的本地视频制作台。所有社交账号为占位；指向的 URL 在生产环境才会跳转到真实平台。</p>
        </section>
        <section className="legalExtra">
          <h2>回到主站</h2>
          <p>访问 <a href="/index.html">index.html</a> 继续操作；社交仅作为内容分发渠道。</p>
        </section>
        <section className="legalFooter">
          <p>其他社交：<a href="/social/twitter.html">X</a> · <a href="/social/youtube.html">YouTube</a> · <a href="/social/linkedin.html">LinkedIn</a> · <a href="/social/tiktok.html">TikTok</a> · <a href="/social/github.html">GitHub</a></p>
        </section>
      </section>
      <Footer />
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<React.StrictMode><SocialLanding /></React.StrictMode>);
