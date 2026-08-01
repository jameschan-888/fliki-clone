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
