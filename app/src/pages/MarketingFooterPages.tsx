import React from "react";
import { Footer } from "../components/layout/Footer";

// Marketing Footer 独立页 (Legal + Resources + Company). 16 页与 Footer.tsx 的链接一一对应.
// 复用 CatalogPages 的 catalogPage / catalogNav / catalogHero 样式, 新增 .legalPage/.legalSection/.legalBody/.legalMeta/.legalHero/.legalFooter/.legalExtra.

export function TermsPage() {
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
        <span className="eyebrow">LEGAL</span>
        <h1>Terms of Service</h1>
        <p>使用本地视频制作台前请阅读的服务条款。</p>
        <div className="legalMeta">生效日期 / 更新时间：2026-08-01</div>
      </section>
      <section className="legalBody">
        <section className="legalSection" key={"terms-sec-1. 服务范围"}><h2>1. 服务范围</h2><p>本平台允许你使用脚本、模板、媒体和 AI Provider 创建视频草稿、保存到 workspace 并与协作成员分享。免费账户包含每月有限 minutes 数；付费订阅按所选 plan 配额执行。</p></section><section className="legalSection" key={"terms-sec-2. 账户责任"}><h2>2. 账户责任</h2><p>你对自己的登录凭据、提交内容、协作邀请负责。任何由你账户产生的 Provider 调用费用，按月度账单结算。</p></section><section className="legalSection" key={"terms-sec-3. 可接受内容"}><h2>3. 可接受内容</h2><p>禁止上传违法、抄袭、未授权他人肖像或声音的内容。详细条款见 Acceptable Use Policy。</p></section><section className="legalSection" key={"terms-sec-4. 服务变更与中止"}><h2>4. 服务变更与中止</h2><p>我们保留为安全、合规或产品演进而升级服务的权利；会通过站内公告和邮件提前通知重大变更。</p></section><section className="legalSection" key={"terms-sec-5. 免责声明"}><h2>5. 免责声明</h2><p>AI 生成内容可能不准确或存在偏差，请在使用前对事实性和合规性做人工复核。</p></section><section className="legalSection" key={"terms-sec-6. 适用法律"}><h2>6. 适用法律</h2><p>本条款适用中华人民共和国法律；争议优先友好协商，协商不成提交平台所在地有管辖权的人民法院。</p></section>
        
        <section className="legalFooter">
          <p>本文档与 <a href="/terms.html">Terms</a>、<a href="/privacy.html">Privacy</a>、<a href="/security.html">Security</a> 一并构成协议。</p>
          <p>需要帮助？联系 <a href="/contact.html">Sales</a>。</p>
        </section>
      </section>
      <Footer />
    </main>
  );
}


export function PrivacyPage() {
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
        <span className="eyebrow">LEGAL</span>
        <h1>隐私政策</h1>
        <p>我们如何收集、使用和保护你的数据。</p>
        <div className="legalMeta">生效日期 / 更新时间：2026-08-01</div>
      </section>
      <section className="legalBody">
        <section className="legalSection" key={"privacy-sec-我们收集的内容"}><h2>我们收集的内容</h2><p>账户信息（邮箱、姓名）、提交的工作流内容、Provider API key 的本地密文、IP 与设备信息用于安全审计。</p></section><section className="legalSection" key={"privacy-sec-如何使用"}><h2>如何使用</h2><p>用于账户标识、计费、协作分享、Provider 调度、安全审计，并改进产品体验。</p></section><section className="legalSection" key={"privacy-sec-数据存储与跨境"}><h2>数据存储与跨境</h2><p>本地 SQLite 存储元数据；媒体文件保存在 outputs/ 目录。用户主动选择海外 Provider 时，相关调用可能跨境传输。</p></section><section className="legalSection" key={"privacy-sec-你的权利"}><h2>你的权利</h2><p>可随时下载你的内容、撤回 API key、删除草稿与账户；行使权利请联系 privacy@local.example。</p></section><section className="legalSection" key={"privacy-sec-共享与出售"}><h2>共享与出售</h2><p>我们不向第三方出售你的内容。仅在你明确邀请协作或公开分享 token 时，相应链接可被对应成员访问。</p></section><section className="legalSection" key={"privacy-sec-联系 DPO"}><h2>联系 DPO</h2><p>dpo@local.example。响应时效：收到后 15 个工作日内。</p></section>
        
        <section className="legalFooter">
          <p>本文档与 <a href="/terms.html">Terms</a>、<a href="/privacy.html">Privacy</a>、<a href="/security.html">Security</a> 一并构成协议。</p>
          <p>需要帮助？联系 <a href="/contact.html">Sales</a>。</p>
        </section>
      </section>
      <Footer />
    </main>
  );
}


export function CookiesPage() {
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
        <span className="eyebrow">LEGAL</span>
        <h1>Cookie 政策</h1>
        <p>本站仅使用必要 Cookie 与本地存储。</p>
        <div className="legalMeta">生效日期 / 更新时间：2026-08-01</div>
      </section>
      <section className="legalBody">
        <section className="legalSection" key={"cookies-sec-必要 Cookie"}><h2>必要 Cookie</h2><p>用于登录会话、X-Request-ID 防重、XSS token。关闭后无法使用核心功能。</p></section><section className="legalSection" key={"cookies-sec-本地存储"}><h2>本地存储</h2><p>我们使用 localStorage 保存品牌色板、Logo 水印、订阅/草稿偏好，仅在本机。</p></section><section className="legalSection" key={"cookies-sec-分析 Cookie"}><h2>分析 Cookie</h2><p>默认关闭；开启时可匿名统计页面访问用于产品优化。</p></section><section className="legalSection" key={"cookies-sec-管理 Cookie"}><h2>管理 Cookie</h2><p>你可在浏览器设置中删除或拦截 Cookie，但部分功能可能受影响。</p></section>
        
        <section className="legalFooter">
          <p>本文档与 <a href="/terms.html">Terms</a>、<a href="/privacy.html">Privacy</a>、<a href="/security.html">Security</a> 一并构成协议。</p>
          <p>需要帮助？联系 <a href="/contact.html">Sales</a>。</p>
        </section>
      </section>
      <Footer />
    </main>
  );
}


export function GdprPage() {
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
        <span className="eyebrow">LEGAL</span>
        <h1>GDPR 与数据处理协议</h1>
        <p>面向欧盟 / EEA 数据主体的合规说明。</p>
        <div className="legalMeta">生效日期 / 更新时间：2026-08-01</div>
      </section>
      <section className="legalBody">
        <section className="legalSection" key={"gdpr-sec-控制者与处理者"}><h2>控制者与处理者</h2><p>你作为数据控制者；本平台作为数据处理者，按你指示处理与跨境传输。</p></section><section className="legalSection" key={"gdpr-sec-数据处理协议 (DPA)"}><h2>数据处理协议 (DPA)</h2><p>包含在 Standard Contractual Clauses (SCC) 中的处理范围、机密性承诺与违约通知时限。</p></section><section className="legalSection" key={"gdpr-sec-数据主体请求"}><h2>数据主体请求</h2><p>我们提供导出、删除、限制处理等接口；亦可联系 DPO 由人工处理。</p></section><section className="legalSection" key={"gdpr-sec-事故通报"}><h2>事故通报</h2><p>发现个人数据泄露时，72 小时内通知受影响的控制者与监管机构。</p></section>
        
        <section className="legalFooter">
          <p>本文档与 <a href="/terms.html">Terms</a>、<a href="/privacy.html">Privacy</a>、<a href="/security.html">Security</a> 一并构成协议。</p>
          <p>需要帮助？联系 <a href="/contact.html">Sales</a>。</p>
        </section>
      </section>
      <Footer />
    </main>
  );
}


export function AupPage() {
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
        <span className="eyebrow">LEGAL</span>
        <h1>可接受使用政策</h1>
        <p>禁止的内容类型与违规处理流程。</p>
        <div className="legalMeta">生效日期 / 更新时间：2026-08-01</div>
      </section>
      <section className="legalBody">
        <section className="legalSection" key={"aup-sec-禁止内容"}><h2>禁止内容</h2><p>违法、暴力、色情、仇恨、欺诈、涉及未成年人的不当内容；侵犯他人版权、商标、肖像权、隐私。</p></section><section className="legalSection" key={"aup-sec-禁止行为"}><h2>禁止行为</h2><p>绕过配额、刷量、滥用 Provider API key、绕过内容审核机制。</p></section><section className="legalSection" key={"aup-sec-审核与处置"}><h2>审核与处置</h2><p>收到举报或检测到疑似违规后，先隐藏并通知你；多次或严重违规将终止账户并保留法律追究权利。</p></section><section className="legalSection" key={"aup-sec-申诉"}><h2>申诉</h2><p>收到处置通知后 14 天内可提交申诉；提供申诉通道：aup@local.example。</p></section>
        
        <section className="legalFooter">
          <p>本文档与 <a href="/terms.html">Terms</a>、<a href="/privacy.html">Privacy</a>、<a href="/security.html">Security</a> 一并构成协议。</p>
          <p>需要帮助？联系 <a href="/contact.html">Sales</a>。</p>
        </section>
      </section>
      <Footer />
    </main>
  );
}


export function SecurityPage() {
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
        <span className="eyebrow">LEGAL</span>
        <h1>安全实践</h1>
        <p>安全头、CORS 白名单、审计日志、密钥管理。</p>
        <div className="legalMeta">生效日期 / 更新时间：2026-08-01</div>
      </section>
      <section className="legalBody">
        <section className="legalSection" key={"security-sec-传输安全"}><h2>传输安全</h2><p>生产环境强制 HTTPS；本地开发通过 X-Request-ID 与 SecureMiddleware 校验 Origin。</p></section><section className="legalSection" key={"security-sec-访问控制"}><h2>访问控制</h2><p>JWT access + refresh 双 token；refresh 一次性使用并写入撤销表；CORS 仅允许配置域名。</p></section><section className="legalSection" key={"security-sec-密钥管理"}><h2>密钥管理</h2><p>Provider API key 通过环境变量注入；可选磁盘 AES-GCM 加密存储（路径 ~/secrets/.fliki_provider_secrets.json）。</p></section><section className="legalSection" key={"security-sec-审计与告警"}><h2>审计与告警</h2><p>所有创建/删除/分享动作写入 audit_logs；P1-B alerts 在 4 条规则触发时通过 webhook 通知。</p></section><section className="legalSection" key={"security-sec-漏洞报告"}><h2>漏洞报告</h2><p>security@local.example；负责任披露期限 90 天。</p></section>
        
        <section className="legalFooter">
          <p>本文档与 <a href="/terms.html">Terms</a>、<a href="/privacy.html">Privacy</a>、<a href="/security.html">Security</a> 一并构成协议。</p>
          <p>需要帮助？联系 <a href="/contact.html">Sales</a>。</p>
        </section>
      </section>
      <Footer />
    </main>
  );
}


export function HelpPage() {
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
        <span className="eyebrow">RESOURCES</span>
        <h1>帮助中心</h1>
        <p>从第一次登录到多人协作的全流程答疑。</p>
        <div className="legalMeta">生效日期 / 更新时间：持续更新</div>
      </section>
      <section className="legalBody">
        <section className="legalSection" key={"help-sec-开始之前"}><h2>开始之前</h2><p>准备好一段脚本（≥100 字），决定视频风格，登录后新建草稿即可。</p></section><section className="legalSection" key={"help-sec-AI 出片瓶颈"}><h2>AI 出片瓶颈</h2><p>大部分生成失败发生在外部 Provider 的 API key 缺失或配额耗尽；用 Provider Key Manager 一键配置。</p></section><section className="legalSection" key={"help-sec-分享与协作"}><h2>分享与协作</h2><p>所有草稿归属 Workspace；可邀请成员、生成 share token、嵌入第三方网站。</p></section><section className="legalSection" key={"help-sec-免费 vs 付费"}><h2>免费 vs 付费</h2><p>免费账户每月 30 分钟生成额度，Standard 300 分钟，Pro 1500 分钟；超出按 credits 单独计费。</p></section>
        <section className="legalExtra" key="help-extra"><h2>补充说明</h2><p>常见问题：脚本字数、语音选择、字幕语言、品牌色板保存位置、删除草稿与回收站。</p></section>
        <section className="legalFooter">
          <p>本文档与 <a href="/terms.html">Terms</a>、<a href="/privacy.html">Privacy</a>、<a href="/security.html">Security</a> 一并构成协议。</p>
          <p>需要帮助？联系 <a href="/contact.html">Sales</a>。</p>
        </section>
      </section>
      <Footer />
    </main>
  );
}


export function ChangelogPage() {
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
        <span className="eyebrow">RESOURCES</span>
        <h1>产品更新</h1>
        <p>最近一周的功能与修复。</p>
        <div className="legalMeta">生效日期 / 更新时间：每周三发布</div>
      </section>
      <section className="legalBody">
        <section className="legalSection" key={"changelog-sec-2026-08-04 B/C 全栈收口"}><h2>2026-08-04 B/C 全栈收口</h2><p>Editor 加 5 个工具面板（Copilot/Character/Elements/Record/Layers），Record/Translate 接入 ASR/MT MVP。</p></section><section className="legalSection" key={"changelog-sec-2026-08-03 计费与协作"}><h2>2026-08-03 计费与协作</h2><p>subscriptions/credit_ledger/share_links/workspace_brand_kits 上线；工作流创建时按 X-Request-ID 幂等扣 credit。</p></section><section className="legalSection" key={"changelog-sec-2026-08-02 路由拆分"}><h2>2026-08-02 路由拆分</h2><p>main.py 拆到 routers/&#123;analytics,render,startup,alerts&#125;；反向依赖 `from main import get_db` 重构为 Depends(get_db)。</p></section><section className="legalSection" key={"changelog-sec-2026-08-01 安全门"}><h2>2026-08-01 安全门</h2><p>CORS 白名单 + SecureMiddleware；JWT refresh 一次性 + 撤销表；X-Request-ID 全链路。</p></section><section className="legalSection" key={"changelog-sec-更早版本"}><h2>更早版本</h2><p>P4-P5 阶段：Workflow Drafts + Scenes/Segments 编辑器 + Provider 矩阵 + DuckDB 兼容 + Remotion 渲染。</p></section>
        
        <section className="legalFooter">
          <p>本文档与 <a href="/terms.html">Terms</a>、<a href="/privacy.html">Privacy</a>、<a href="/security.html">Security</a> 一并构成协议。</p>
          <p>需要帮助？联系 <a href="/contact.html">Sales</a>。</p>
        </section>
      </section>
      <Footer />
    </main>
  );
}


export function AffiliatePage() {
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
        <span className="eyebrow">RESOURCES</span>
        <h1>推广计划</h1>
        <p>分享链接，按结算周期返回 25% 订阅费。</p>
        <div className="legalMeta">生效日期 / 更新时间：滚动报名</div>
      </section>
      <section className="legalBody">
        <section className="legalSection" key={"affiliate-sec-佣金结构"}><h2>佣金结构</h2><p>Standard 25%、Pro 30%；通过专属 referral link 注册的新用户在订阅有效期内持续计入。</p></section><section className="legalSection" key={"affiliate-sec-结算与提现"}><h2>结算与提现</h2><p>每月 1 号结算上月收入，最低 50 元起提现；通过支付宝或银行转账处理。</p></section><section className="legalSection" key={"affiliate-sec-禁止行为"}><h2>禁止行为</h2><p>禁止自荐、虚假陈述、批量注册；违反将取消当月所有佣金。</p></section><section className="legalSection" key={"affiliate-sec-如何加入"}><h2>如何加入</h2><p>发送邮件到 partners@local.example，附你的使用场景 + 受众规模。</p></section>
        
        <section className="legalFooter">
          <p>本文档与 <a href="/terms.html">Terms</a>、<a href="/privacy.html">Privacy</a>、<a href="/security.html">Security</a> 一并构成协议。</p>
          <p>需要帮助？联系 <a href="/contact.html">Sales</a>。</p>
        </section>
      </section>
      <Footer />
    </main>
  );
}


export function DocsApiPage() {
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
        <span className="eyebrow">RESOURCES</span>
        <h1>API 文档</h1>
        <p>通过 REST + JSON 与本地视频制作台通信。</p>
        <div className="legalMeta">生效日期 / 更新时间：实时跟随代码</div>
      </section>
      <section className="legalBody">
        <section className="legalSection" key={"docs-api-sec-认证"}><h2>认证</h2><p>POST /auth/login 取得 access_token；refresh 通过 POST /auth/refresh 一次性轮换。</p></section><section className="legalSection" key={"docs-api-sec-草稿"}><h2>草稿</h2><p>POST /workflow-drafts 创建；PATCH 改场景；POST /workflow-drafts/{'{'}'id'{'}'}/render 触发成片。</p></section><section className="legalSection" key={"docs-api-sec-计费"}><h2>计费</h2><p>GET /billing/balance 查询余额；credits 在 Provider 调用前扣减，幂等。</p></section><section className="legalSection" key={"docs-api-sec-公开分享"}><h2>公开分享</h2><p>POST /workflow-drafts/{'{'}'id'{'}'}/share 创建只读 token；GET /share/{'{'}'token'{'}'} 不需登录。</p></section><section className="legalSection" key={"docs-api-sec-OpenAPI"}><h2>OpenAPI</h2><p>运行中的服务在 /openapi.json 暴露完整 schema；可导入 Postman / Insomnia。</p></section>
        <section className="legalExtra" key="docs-api-extra"><h2>补充说明</h2><p>速率限制：未认证 60 req/min；认证后 600 req/min；超过返 429。</p></section>
        <section className="legalFooter">
          <p>本文档与 <a href="/terms.html">Terms</a>、<a href="/privacy.html">Privacy</a>、<a href="/security.html">Security</a> 一并构成协议。</p>
          <p>需要帮助？联系 <a href="/contact.html">Sales</a>。</p>
        </section>
      </section>
      <Footer />
    </main>
  );
}


export function BrandKitsPage() {
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
        <span className="eyebrow">RESOURCES</span>
        <h1>品牌套件指南</h1>
        <p>5 预设色板 + 4 主色 + 字体 + Logo + 水印。</p>
        <div className="legalMeta">生效日期 / 更新时间：永久</div>
      </section>
      <section className="legalBody">
        <section className="legalSection" key={"brand-kits-sec-色板选择"}><h2>色板选择</h2><p>从 5 套预设（科技 / 商务 / 教育 / 创意 / 生活）选一套，或自定 4 色。</p></section><section className="legalSection" key={"brand-kits-sec-字体"}><h2>字体</h2><p>标题 / 正文字体独立配置；保存后所有模板与字幕生成沿用。</p></section><section className="legalSection" key={"brand-kits-sec-Logo 与水印"}><h2>Logo 与水印</h2><p>上传 PNG/SVG；可调节位置（4 角）、透明度（10%-100%）、大小（5%-30%）。</p></section><section className="legalSection" key={"brand-kits-sec-何时生效"}><h2>何时生效</h2><p>保存即时写回第一个 Workspace；下次打开草稿自动加载。</p></section>
        
        <section className="legalFooter">
          <p>本文档与 <a href="/terms.html">Terms</a>、<a href="/privacy.html">Privacy</a>、<a href="/security.html">Security</a> 一并构成协议。</p>
          <p>需要帮助？联系 <a href="/contact.html">Sales</a>。</p>
        </section>
      </section>
      <Footer />
    </main>
  );
}


export function StatusPage() {
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
        <span className="eyebrow">RESOURCES</span>
        <h1>系统状态</h1>
        <p>当前可用性指标与最近 30 天事件。</p>
        <div className="legalMeta">生效日期 / 更新时间：实时</div>
      </section>
      <section className="legalBody">
        <section className="legalSection" key={"status-sec-服务可用"}><h2>服务可用</h2><p>Backend API、Remotion 渲染、Provider 矩阵：所有均处于 OPERATIONAL。</p></section><section className="legalSection" key={"status-sec-性能"}><h2>性能</h2><p>P95 API 响应 &#60;350ms；Render 队列满载 &#60;10；磁盘剩余 47GB。</p></section><section className="legalSection" key={"status-sec-告警"}><h2>告警</h2><p>P1-B 4 条规则（queue_depth_high / render_consecutive_fail / 5xx_spike / workflow_failed_spike）当前 0 触发。</p></section><section className="legalSection" key={"status-sec-历史事件"}><h2>历史事件</h2><p>详见 docs/status-history.md；过去 30 天无 P1 故障。</p></section>
        <section className="legalExtra" key="status-extra"><h2>补充说明</h2><p>如何订阅状态变化？发送邮件到 status@local.example 订阅。</p></section>
        <section className="legalFooter">
          <p>本文档与 <a href="/terms.html">Terms</a>、<a href="/privacy.html">Privacy</a>、<a href="/security.html">Security</a> 一并构成协议。</p>
          <p>需要帮助？联系 <a href="/contact.html">Sales</a>。</p>
        </section>
      </section>
      <Footer />
    </main>
  );
}


export function AboutPage() {
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
        <span className="eyebrow">COMPANY</span>
        <h1>关于我们</h1>
        <p>本地优先的视频工作流底座，让 AI 出片落到你的工作流里。</p>
        <div className="legalMeta">生效日期 / 更新时间：常驻</div>
      </section>
      <section className="legalBody">
        <section className="legalSection" key={"about-sec-我们是谁"}><h2>我们是谁</h2><p>一支 7 人团队，主要位于上海、深圳、新加坡。专注把 AI 视频生成变成可嵌入、可审计、可协作的产品。</p></section><section className="legalSection" key={"about-sec-我们的信念"}><h2>我们的信念</h2><p>创作者应保留对素材与品牌的完全控制；企业应保留对调用链路的可观测；研究者应保留对原模型的可替换。</p></section><section className="legalSection" key={"about-sec-里程碑"}><h2>里程碑</h2><p>2025-Q2 立项；2025-Q4 内部 alpha；2026-Q2 公开 MVP；2026-Q3 引入 Brand Kit + 计费。</p></section>
        
        <section className="legalFooter">
          <p>本文档与 <a href="/terms.html">Terms</a>、<a href="/privacy.html">Privacy</a>、<a href="/security.html">Security</a> 一并构成协议。</p>
          <p>需要帮助？联系 <a href="/contact.html">Sales</a>。</p>
        </section>
      </section>
      <Footer />
    </main>
  );
}


export function CareersPage() {
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
        <span className="eyebrow">COMPANY</span>
        <h1>加入我们</h1>
        <p>工程、设计、AI 研究、产品、客户成功 多岗位开放。</p>
        <div className="legalMeta">生效日期 / 更新时间：滚动招聘</div>
      </section>
      <section className="legalBody">
        <section className="legalSection" key={"careers-sec-工作方式"}><h2>工作方式</h2><p>远程为主，每季度一次 3 天线下。鼓励跨职能轮岗。</p></section><section className="legalSection" key={"careers-sec-薪酬"}><h2>薪酬</h2><p>对标市场 75 分位；股权按贡献分配；学习预算每年 1 万元。</p></section><section className="legalSection" key={"careers-sec-正在招聘"}><h2>正在招聘</h2><p>Senior Backend (FastAPI/SQLite)、Senior Frontend (React/TS)、AI Infra (Remotion/Provider 调度)、Designer。</p></section><section className="legalSection" key={"careers-sec-如何申请"}><h2>如何申请</h2><p>jobs@local.example，附 GitHub 或作品集；面试 3 轮：电话 + 技术 + 文化。</p></section>
        
        <section className="legalFooter">
          <p>本文档与 <a href="/terms.html">Terms</a>、<a href="/privacy.html">Privacy</a>、<a href="/security.html">Security</a> 一并构成协议。</p>
          <p>需要帮助？联系 <a href="/contact.html">Sales</a>。</p>
        </section>
      </section>
      <Footer />
    </main>
  );
}


export function PressPage() {
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
        <span className="eyebrow">COMPANY</span>
        <h1>媒体资料</h1>
        <p>Logo、截图、数据点与官方口径。</p>
        <div className="legalMeta">生效日期 / 更新时间：随时更新</div>
      </section>
      <section className="legalBody">
        <section className="legalSection" key={"press-sec-官方名称"}><h2>官方名称</h2><p>本地视频制作台 / Local Video Studio</p></section><section className="legalSection" key={"press-sec-主要数据"}><h2>主要数据</h2><p>已生成 50,000+ 段视频；30+ Provider 接入；可工作语种 14 种。</p></section><section className="legalSection" key={"press-sec-Logo"}><h2>Logo</h2><p>下载：/press/logo.svg；PNG 三种尺寸打包。</p></section><section className="legalSection" key={"press-sec-媒体联系人"}><h2>媒体联系人</h2><p>press@local.example；采访请求 24 小时内回复。</p></section>
        
        <section className="legalFooter">
          <p>本文档与 <a href="/terms.html">Terms</a>、<a href="/privacy.html">Privacy</a>、<a href="/security.html">Security</a> 一并构成协议。</p>
          <p>需要帮助？联系 <a href="/contact.html">Sales</a>。</p>
        </section>
      </section>
      <Footer />
    </main>
  );
}


export function ContactPage() {
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
        <span className="eyebrow">COMPANY</span>
        <h1>联系我们</h1>
        <p>500+ 席企业版 / 私有 Provider / SLA 谈判三通道。</p>
        <div className="legalMeta">生效日期 / 更新时间：工作日 9:00-19:00</div>
      </section>
      <section className="legalBody">
        <section className="legalSection" key={"contact-sec-销售邮箱"}><h2>销售邮箱</h2><p>sales@local.example；通常 4 小时内回复。</p></section><section className="legalSection" key={"contact-sec-企业版"}><h2>企业版</h2><p>500+ 席位、SSO/SAML、私有部署、自带 Provider；按年报价。</p></section><section className="legalSection" key={"contact-sec-私有 Provider"}><h2>私有 Provider</h2><p>MiniMax 内网、Azure OpenAI、本地 GPU 集群均可接入；联调 2-4 周。</p></section><section className="legalSection" key={"contact-sec-SLA"}><h2>SLA</h2><p>P1 &#60;30 分钟响应，每月 &#60;4 小时不可用；超时按月费 10% 抵扣。</p></section>
        <section className="legalExtra" key="contact-extra"><h2>补充说明</h2><p>紧急安全漏洞请走 security@local.example。</p></section>
        <section className="legalFooter">
          <p>本文档与 <a href="/terms.html">Terms</a>、<a href="/privacy.html">Privacy</a>、<a href="/security.html">Security</a> 一并构成协议。</p>
          <p>需要帮助？联系 <a href="/contact.html">Sales</a>。</p>
        </section>
      </section>
      <Footer />
    </main>
  );
}

