import React from "react";

const COLS = [
  {
    title: "Product",
    links: [
      { label: "Idea to Video", href: "/features.html#idea-to-video" },
      { label: "Script to Video", href: "/drafts.html" },
      { label: "Blog to Video", href: "/blog.html" },
      { label: "PPT to Video", href: "/ppt.html" },
      { label: "AI Avatar", href: "/avatars.html" },
      { label: "Voice Cloning", href: "/voices.html" },
      { label: "Templates", href: "/templates.html" },
      { label: "Pricing", href: "/pricing.html" },
    ],
  },
  {
    title: "Resources",
    links: [
      { label: "Help Center", href: "/help.html" },
      { label: "Changelog", href: "/changelog.html" },
      { label: "Affiliate Program", href: "/affiliate.html" },
      { label: "API Documentation", href: "/docs-api.html" },
      { label: "Brand Kit Guide", href: "/brand-kits.html" },
      { label: "System Status", href: "/status.html" },
    ],
  },
  {
    title: "Company",
    links: [
      { label: "About Us", href: "/about.html" },
      { label: "Careers", href: "/careers.html" },
      { label: "Press", href: "/press.html" },
      { label: "Contact Sales", href: "/contact.html" },
    ],
  },
  {
    title: "Use Cases",
    links: [
      { label: "Marketing & Ads", href: "/use-cases.html#marketing" },
      { label: "Social Media (TikTok/Reels)", href: "/use-cases.html#social" },
      { label: "Sales Outreach", href: "/use-cases.html#sales" },
      { label: "Product Training & L&D", href: "/use-cases.html#training" },
      { label: "Educational Courses", href: "/use-cases.html#education" },
      { label: "Ecommerce Product Videos", href: "/use-cases.html#ecommerce" },
      { label: "Localization", href: "/use-cases.html#localization" },
    ],
  },
  {
    title: "Legal",
    links: [
      { label: "Terms of Service", href: "/terms.html" },
      { label: "Privacy Policy", href: "/privacy.html" },
      { label: "Cookie Policy", href: "/cookies.html" },
      { label: "GDPR / DPA", href: "/gdpr.html" },
      { label: "Acceptable Use", href: "/aup.html" },
      { label: "Security", href: "/security.html" },
    ],
  },
];

export function Footer() {
  return (
    <footer className="footer">
      <div className="footer-grid">
        {COLS.map((col) => (
          <div key={col.title} className="footer-col">
            <h4>{col.title}</h4>
            <ul>
              {col.links.map((l) => (
                <li key={l.label}><a href={l.href}>{l.label}</a></li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <div className="footer-bottom">
        <a className="brand" href="/index.html"><span className="dot"></span>本地视频制作台</a>
        <div className="social">
          <a href="/social/twitter" aria-label="Twitter">X</a>
          <a href="/social/youtube" aria-label="YouTube">YT</a>
          <a href="/social/linkedin" aria-label="LinkedIn">in</a>
          <a href="/social/tiktok" aria-label="TikTok">TT</a>
          <a href="/social/github" aria-label="GitHub">GH</a>
        </div>
        <div className="meta">
          <div>© 2026 Local Video Studio. Inspired by Fliki.ai architecture.</div>
          <div className="legal" style={{ marginTop: 6 }}>
            <a href="/terms.html">Terms</a>
            <a href="/privacy.html">Privacy</a>
            <a href="/cookies.html">Cookies</a>
            <a href="/security.html">Security</a>
          </div>
        </div>
      </div>
    </footer>
  );
}

export default Footer;
