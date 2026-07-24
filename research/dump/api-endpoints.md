# Fliki tRPC API Endpoints (api.production.fliki.ai)

Captured from app.fliki.ai editor session on 2026-07-23.

## Transport

- Pattern: `GET /rpc/<endpointA>,<endpointB>,.../...?batch=1&input={"0":{"...":...},"1":{"...":...}}`
- Auth: `Authorization: Bearer <JWT>` (HS256, 24-byte hex userId claim)
- Headers: `x-device-id`, `x-session-id`, `trpc-accept: application/jsonl`
- Server: Express + Google CDN, `x-powered-by: Express`, CORS open
- Body: JSON list of `{result: {data: ...}}` per endpoint index

## Auth / User

| Method | Endpoint | Purpose |
| ------ | -------- | ------- |
| GET | `user.detail` | Current user profile |
| GET | `subscriptions.active` | Current plan + limits |
| GET | `credit.detail` | Credit balance + daily records |
| GET | `userPlatform.list` | Connected platforms (YouTube, TikTok) |
| GET | `apiAccess.detail` | User API tokens |

## File / Drive

| Method | Endpoint | Purpose |
| ------ | -------- | ------- |
| GET | `drive.list` | Folder/file list (paginated, recursive) |
| GET | `drive.detail` | Single drive entry by driveId |
| POST | `drive.create` | New drive (project/folder) |
| POST | `drive.update` | Rename/move/trash |
| GET | `page.listByCategory` | Pages grouped by category |

## Project / Playback

| Method | Endpoint | Purpose |
| ------ | -------- | ------- |
| GET | `playback.detail` | Load full playback (scenes + layers) |
| POST | `playback.save` | Persist edits |
| GET | `render.latest` | Latest render job status |
| GET | `workflow.detailByPlayback` | Workflow template that produced this file |

## Voice / Language / Pronunciation

| Method | Endpoint | Purpose |
| ------ | -------- | ------- |
| GET | `language.listWithDialects` | 80+ languages + dialects tree |
| GET | `pronunciation.list` | Custom pronunciation rules |

## Media / Asset

| Method | Endpoint | Purpose |
| ------ | -------- | ------- |
| GET | `font.list` | Custom font list (currently empty for free user) |
| GET | `notification.list` | In-app notification feed |
| GET | `release.list` | Changelog/release notes |

## Observed batched call (home page load)

```
GET /rpc/subscriptions.active,notification.list,drive.list,page.listByCategory,language.listWithDialects?batch=1&input={"2":{"format":"video","limit":6,"isFolder":false,"recursive":true,"hideTeamFolder":true,"sortKey":"updatedAt"},"3":{"category":"tutorials"}}
```

## Observed batched call (editor open)

```
GET /rpc/userPlatform.list,apiAccess.detail,pronunciation.list,playback.detail,workflow.detailByPlayback,drive.detail,font.list?batch=1&input={"2":{"playbackId":"6a619e527b6a4072b66692cd"},"3":{"playbackId":"6a619e527b6a4072b66692cd"},"4":{"playbackId":"6a619e527b6a4072b66692cd"},"5":{"driveId":"6a619e527b6a4072b66692d4"}}
```

## CDN domains

- `cdn.fliki.ai/media.v2/generated/<userId>/<id>.mp3` - generated TTS audio
- `cdn.fliki.ai/media.v2/stock/storyblocks/<id>_thumb.jpg` - stock thumbnails
- `cdn.fliki.ai/media.v2/my/image/<id>_preview.jpg` - user playground images
- `cdn.fliki.ai/media.v2/temp/<id>.webm` - recipe preview clips

## Analytics / 3rd party

- `analytics.fliki.ai/e/?...` - PostHog self-hosted (backend)
- `analytics.fliki.ai/flags/?...` - PostHog feature flags
- `metrics.fliki.ai/g/collect?v=2` - GA4
- `h.clarity.ms/collect` - Microsoft Clarity heatmap
- `www.googletagmanager.com/gtm.js?id=GTM-597LV723` - GTM container
- `ov-1d104299d2a447049cdc73700c9309f7.ecs.us-west-2.on.aws/events` - ? (AWS endpoint)
- `api.churnkey.co/v1/api/orgs/ejd88fxt3/passive/config` - ChurnKey cancel-save modal

## Implication for local clone

- We do NOT need to replicate tRPC. Use plain REST + JSON (FastAPI).
- Real-time collab is absent; single-user editor, no websocket.
- JWT auth can be replaced with simple session cookie or local-only mode.
- 80+ languages + 67+ stock characters + 5 recipes = baseline library to seed.
