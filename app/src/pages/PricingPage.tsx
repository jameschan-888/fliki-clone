import { useState } from "react";

type Cycle = "monthly" | "annual";

type Plan = {
  id: string;
  name: string;
  price: { monthly: string; annual: string; old?: string };
  desc: string;
  cta: string;
  href: string;
  featured?: boolean;
  bullets: Array<{ text: string; no?: boolean }>;
};

const PLANS: Plan[] = [
  {
    id: "free",
    name: "Free",
    price: { monthly: "$0", annual: "$0" },
    desc: "无需信用卡, 体验所有核心工作流. 适合个人尝鲜.",
    cta: "免费开始",
    href: "/signup.html",
    bullets: [
      { text: "36 credits / 月" },
      { text: "300 声音 (80+ 语言)" },
      { text: "工作流受限 (Limited)" },
      { text: "HD 720p 输出" },
      { text: "带 Fliki 水印" },
      { text: "AI 图像生成", no: true },
      { text: "Voice cloning", no: true },
    ],
  },
  {
    id: "standard",
    name: "Standard",
    price: { monthly: "$28", annual: "$21", old: "$28" },
    desc: "年付 $21/月, 180 分钟 credit, 适合独立创作者与小型团队.",
    cta: "选 Standard",
    href: "/signup.html",
    featured: true,
    bullets: [
      { text: "2,160 credits / 年" },
      { text: "1,000 声音 (含 500 真人级)" },
      { text: "Full 工作流 + 1 个 Series" },
      { text: "1080p 全高清 + 15 分钟" },
      { text: "Voice cloning (1 个) + 限量 avatar" },
      { text: "AI Playground + 商用授权" },
      { text: "AI Copilot + Zapier 集成" },
    ],
  },
  {
    id: "premium",
    name: "Premium",
    price: { monthly: "$88", annual: "$66", old: "$88" },
    desc: "年付 $66/月, 7200 credits, 适合高产能团队与机构.",
    cta: "选 Premium",
    href: "/signup.html",
    bullets: [
      { text: "7,200 credits / 年" },
      { text: "2,000+ 声音 (含 1000+ 表情级)" },
      { text: "40 分钟单视频 + 3 个 Series" },
      { text: "AI 视频片段 + 多 voice cloning" },
      { text: "全部 avatar + 多个 brand kit" },
      { text: "API 访问 + 优先支持" },
      { text: "团队协作 + 商用授权" },
    ],
  },
  {
    id: "enterprise",
    name: "Enterprise",
    price: { monthly: "Custom", annual: "Custom" },
    desc: "自定义 credit, 品牌定制模板, 专属客户经理.",
    cta: "联系销售",
    href: "/signup.html?plan=enterprise",
    bullets: [
      { text: "自定义 credit 与批量折扣" },
      { text: "API 访问 + 最新模型" },
      { text: "定制 avatar + 专业 voice clone" },
      { text: "品牌定制模板 + 团队协作" },
      { text: "专属客户经理" },
      { text: "发票结算 + SLA" },
      { text: "安全合规 + 赔偿条款" },
    ],
  },
];

const COMPARE: Array<{ feature: string; free: string | boolean; standard: string | boolean; premium: string | boolean; enterprise?: string | boolean }> = [
  { feature: "Credits", free: "36 / 月", standard: "2,160 / 年", premium: "7,200 / 年", enterprise: "Custom" },
  { feature: "Export length", free: "1 min", standard: "15 min", premium: "40 min", enterprise: "Custom" },
  { feature: "Resolution", free: "720p", standard: "1080p", premium: "1080p", enterprise: "4K (Custom)" },
  { feature: "Scene limits", free: "50", standard: "100", premium: "150", enterprise: "Custom" },
  { feature: "Standard voices", free: "300", standard: "1,000", premium: "2,000+", enterprise: "2,000+" },
  { feature: "Ultra-Realistic voices", free: false, standard: "500", premium: "1,000+", enterprise: "1,000+" },
  { feature: "Workflows", free: "Limited", standard: "Full", premium: "Full", enterprise: "Full" },
  { feature: "Publications / 月", free: false, standard: "50", premium: "100", enterprise: "Custom" },
  { feature: "Series", free: false, standard: "1", premium: "3", enterprise: "Custom" },
  { feature: "AI Image", free: true, standard: true, premium: true, enterprise: true },
  { feature: "AI Video clips", free: false, standard: true, premium: true, enterprise: true },
  { feature: "AI Avatar", free: false, standard: "Limited", premium: true, enterprise: "Personalized" },
  { feature: "Voice cloning", free: false, standard: "1", premium: "3", enterprise: "Professional" },
  { feature: "Brand kits", free: false, standard: "1", premium: "3", enterprise: "Custom" },
  { feature: "Bulk create", free: false, standard: true, premium: true, enterprise: true },
  { feature: "AI Copilot", free: false, standard: true, premium: true, enterprise: true },
  { feature: "Make / Zapier", free: false, standard: true, premium: true, enterprise: true },
  { feature: "No watermark", free: false, standard: true, premium: true, enterprise: true },
  { feature: "Commercial rights", free: false, standard: true, premium: true, enterprise: true },
  { feature: "API Access", free: false, standard: false, premium: true, enterprise: true },
  { feature: "Team collaboration", free: false, standard: false, premium: true, enterprise: true },
  { feature: "Support", free: "Email", standard: "Email + 实时聊天", premium: "Email + 优先聊天", enterprise: "专属客户经理" },
];

const WORKFLOWS = [
  { tag: "Video", name: "Idea to Video", desc: "粘贴一句话, 系统生成完整脚本+分镜+配音+字幕+背景音乐, 直接渲染." },
  { tag: "Video", name: "Script to Video", desc: "粘贴脚本 -> AI 分镜 -> 选声音 -> 配画面/字幕/音乐 -> 一键渲染." },
  { tag: "Video", name: "Blog to Video", desc: "URL 抓取 -> 自动总结脚本 -> 8-12 段分镜 -> AI 配音 + 字幕 -> 60 秒视频." },
  { tag: "Video", name: "PPT to Video", desc: "上传 PPT/Google Slides -> 每页自动脚本+画面+配音+字幕+转场." },
  { tag: "Video", name: "Auto-edit Video", desc: "上传原始素材 -> AI 字幕 + 静音段裁剪 + 转场 + 背景音乐." },
  { tag: "Video", name: "Recording to Video", desc: "浏览器录屏 -> ASR 转写 -> 字幕轨 + AI 配音 + 静音段裁剪." },
  { tag: "Audio", name: "Idea to Audio", desc: "一句话播客/有声书概念 -> 自动脚本 + 声音 -> MP3/WAV 导出." },
  { tag: "Audio", name: "Script to Audio", desc: "粘贴长文脚本 -> 多声音对话 + 情绪分段 -> 长音频." },
  { tag: "Audio", name: "Blog to Audio", desc: "URL 文章 -> 总结脚本 -> AI 声音 -> 长音频." },
  { tag: "Image", name: "Idea to Thumbnail", desc: "一句话 -> 文字渲染 + 多画幅 (16:9/9:16/1:1) -> 缩略图." },
  { tag: "Image", name: "Idea to Social Carousel", desc: "一句话主题 -> 多页轮播图 (Instagram/LinkedIn/TikTok)." },
  { tag: "Image", name: "Idea to Presentation", desc: "一句话主题 -> 完整 PPT 模板 + 内容生成." },
];

const FAQS = [
  { q: "Credit 怎么扣?", a: "按生成的音频时长和导出视频时长扣, 月底自动重置未使用部分 (年度 plan 滚动到下一年)." },
  { q: "能用我自己的声音吗?", a: "Standard 起支持 voice cloning (1 个), Premium 支持 3 个, Enterprise 支持专业克隆 + 多语言." },
  { q: "可以商用吗?", a: "Standard 起的所有 plan 都包含完整商用授权 + YouTube 许可音乐; Enterprise 含赔偿条款." },
  { q: "支持哪些支付方式?", a: "USD 定价, 主要信用卡/借记卡、GPay、Apple Pay、本地钱包, 全部支持年付/月付切换." },
  { q: "可以随时取消吗?", a: "在 Account -> Manage billing 一键取消, 取消后剩余周期仍可用至到期日." },
  { q: "团队可以多人协作吗?", a: "Premium 支持基础协作, Enterprise 支持角色权限、SSO、审计日志、专属客户经理." },
];

const CHECK_HTML = "<span class=\"check\">✓</span>";
const DASH_HTML = "<span class=\"dash\">—</span>";

function fmtCell(v: string | boolean): string {
  if (v === true) return CHECK_HTML;
  if (v === false) return DASH_HTML;
  return v;
}

export function PricingPage() {
  const [cycle, setCycle] = useState<Cycle>("annual");
  return (
    <main className="shell">
      <div className="eyebrow">PRICING</div>
      <h1>按用量付费, 不绑死月费</h1>
      <p className="lead">所有 plan 都包含核心 6 大视频工作流 + 6 大音频/图像工作流. credit 按生成量扣, 不浪费.</p>

      <div className="toggle" role="tablist">
        <button className={cycle === "monthly" ? "active" : ""} onClick={() => setCycle("monthly")}>月付</button>
        <button className={cycle === "annual" ? "active" : ""} onClick={() => setCycle("annual")}>年付 (省 25%)</button>
      </div>

      <section className="plans" aria-label="plan 列表">
        {PLANS.map((p) => {
          const price = cycle === "annual" ? p.price.annual : p.price.monthly;
          const showOld = cycle === "annual" && p.price.old;
          return (
            <article key={p.id} className={"plan" + (p.featured ? " featured" : "")}>
              {p.featured && <div className="plan-badge">最受欢迎</div>}
              <div className="plan-name">{p.name}</div>
              <div className="plan-price">
                {price}
                {price.startsWith("$") && <small>/ 月{cycle === "annual" ? " (年付)" : ""}</small>}
                {showOld && <span className="old">{p.price.old}</span>}
              </div>
              <div className="plan-desc">{p.desc}</div>
              <a className={"plan-cta" + (p.featured ? "" : " ghost")} href={p.href}>{p.cta}</a>
              <ul>
                {p.bullets.map((b, i) => (
                  <li key={i} className={b.no ? "no" : ""}>{b.text}</li>
                ))}
              </ul>
            </article>
          );
        })}
      </section>

      <h2 style={{ marginTop: 36, fontSize: 22 }}>详细对比</h2>
      <div className="compare">
        <table>
          <thead>
            <tr>
              <th>功能</th>
              <th>Free</th>
              <th>Standard</th>
              <th>Premium</th>
              <th>Enterprise</th>
            </tr>
          </thead>
          <tbody>
            {COMPARE.map((row, i) => (
              <tr key={i}>
                <td>{row.feature}</td>
                <td dangerouslySetInnerHTML={{ __html: fmtCell(row.free) }} />
                <td dangerouslySetInnerHTML={{ __html: fmtCell(row.standard) }} />
                <td dangerouslySetInnerHTML={{ __html: fmtCell(row.premium) }} />
                <td>{row.enterprise === undefined ? "" : fmtCell(row.enterprise)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2 style={{ marginTop: 48, fontSize: 22 }}>所有 plan 都能跑的工作流</h2>
      <section className="workflows">
        {WORKFLOWS.map((w, i) => (
          <div key={i} className="wf">
            <small>{w.tag}</small>
            <h3>{w.name}</h3>
            <p>{w.desc}</p>
          </div>
        ))}
      </section>

      <h2 style={{ marginTop: 48, fontSize: 22 }}>常见问题</h2>
      <section className="faq">
        {FAQS.map((f, i) => (
          <div key={i} className="faq-item">
            <h4>{f.q}</h4>
            <p>{f.a}</p>
          </div>
        ))}
      </section>

      <div className="cta-strip">
        <h2>今天就开第一条视频</h2>
        <p>免费 plan 无需信用卡, 30 秒注册即可开始.</p>
        <a href="/signup.html">免费注册</a>
      </div>
    </main>
  );
}

export default PricingPage;
