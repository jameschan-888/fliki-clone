# Changelog

按 semver, 仅记录对工程交付 / 行为有可见影响的改动. 细节看 git log + HANDOVER_NEXT.md.

## rev35 (2026-08-01) - 可观测与生产化合规
- feat(security): CORS 白名单 (env FLIKI_ALLOWED_ORIGINS) + 4 个安全头 (X-Content-Type-Options, X-Frame-Options, Referrer-Policy, CSP).
- feat(observability): X-Request-ID 自动生成/回传, JSON access log 经 fliki.access logger.
- feat(rate-limit): /auth/login + /auth/register 端点限速 (5/min/IP+email), register 限速置于 role 白名单前置避免探测区分.
- docs: 加入 CHANGELOG, commitlint, pre-commit, CODEOWNERS, PR/Issue 模板.

## rev34 (2026-08-01) - 安全续期 + CI 收口
- feat(security): refresh token 原子轮换 + 复用撤销子链, 公开注册 role 白名单.
- fix(ci): segment_dispatcher worker 错误队列, 集成测试 50 次压力 0 失败.


## rev36 (2026-08-04) - P3.2 home 商业化 + 视觉验收升级 + 5MB 二进制退 history
- feat(visual): visual_diff_fliki 加 diff_metrics, 返 pixel_thr8/pixel_thr32/ssim 三指标 (N41 算法升级基础). `91915e6`
- feat(home): footer 5 列扩 7 列 + 新增 Compare + Solutions 列 (N42 y=9000+ 缺口). `fd25100`
- chore: .gitignore 加 fliki_research/_slice_tmp/ (5MB 切条 untracked 出 history, N44). `d162838`
- test(visual): tests/e2e/test_visual_diff_metrics.py 新 5 case 单测 (self-vs-self, missing-file, legacy ratio, size-mismatch). `5f5f3e3`
- feat(pricing): PricingPage.tsx PLANS 4 档改 3 档, 删 Enterprise entry / type / COMPARE 行 / FAQ 文案 / render 列. pricing.html CSS 4 列改 3 列. `c277d44`
- feat(home): marketing home 加 Plans preview section (3 cards: Free / Standard featured / Premium) 含 monthly/annual toggle JS, 补 N42 y=5000-7000 全白缺口. `d72af9b`
- fix(visual): diff_ratio 用 numpy mask 替换 PIL Image.getdata (Pillow 14 deprecation, N47). `a173e10`
- fix(visual): numpy/skimage 改 lazy try/except; ssim=None 兜底; 6/6 单测 PASS (含 fallback path). `439069e`
- chore(research): 3 张 5MB+ screenshots 退 history (git rm --cached, disk 保留, regenerable). `cadd8f0`

总 9 commits 已推 origin master. N42 下半部 (5000-9859px) 全部 3 缺口段覆盖: 5000-7000 Plans, 8400-9000 Bottom CTA, 9000+ footer 7 列.
