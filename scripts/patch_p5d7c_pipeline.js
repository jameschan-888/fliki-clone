const fs = require('fs');
const P = 'D:/workspace/Fliki视频制作还原/backend/workflow_pipeline.py';
const raw = fs.readFileSync(P);
const isCRLF = raw.includes(Buffer.from([13, 10]));
const EOL = isCRLF ? '\r\n' : '\n';
let src = raw.toString('utf8');

const oldH = 'def _load_avatar_layout(connection):';
const newH = `def _merge_avatar_layout(global_layout, scene_layout):\n    if not isinstance(global_layout, dict):\n        global_layout = None\n    if not isinstance(scene_layout, dict):\n        return global_layout\n    if not global_layout:\n        return scene_layout\n    merged = dict(global_layout)\n    for k, v in scene_layout.items():\n        if isinstance(v, dict) and isinstance(merged.get(k), dict):\n            merged[k] = {**merged[k], **v}\n        else:\n            merged[k] = v\n    return merged\n\n\n${oldH}`;
if (!src.includes(oldH)) { console.error('helper anchor miss'); process.exit(1); }
src = src.replace(oldH, newH);

const oldA = '            rendered_scenes.append({"id":scene["id"],"title":scene["title"],"subtitle":scene["subtitle"],"durationInSeconds":tts.get("duration_seconds") or scene["duration_seconds"],"videoSrc":video_src,"audioSrc":audio_src,"avatarSrc":avatar_src,"avatarFallback":bool(avatar_meta and avatar_meta.get("fallback_used")),"avatarMode":(avatar_meta or {}).get("mode"),"avatarName":(avatar_meta or {}).get("avatar_name")})';
const newA = '            rendered_scenes.append({"id":scene["id"],"title":scene["title"],"subtitle":scene["subtitle"],"durationInSeconds":tts.get("duration_seconds") or scene["duration_seconds"],"videoSrc":video_src,"audioSrc":audio_src,"avatarSrc":avatar_src,"avatarFallback":bool(avatar_meta and avatar_meta.get("fallback_used")),"avatarMode":(avatar_meta or {}).get("mode"),"avatarName":(avatar_meta or {}).get("avatar_name"),"avatarLayout":None})';
if (!src.includes(oldA)) { console.error('rendered_scenes pattern miss'); process.exit(1); }
src = src.replace(oldA, newA);

const oldB = `        global_avatar_layout=_load_avatar_layout(connection)${EOL}        music["duration_seconds"]=media_duration(music["local_path"]);upsert_asset(connection,run_id,scenes[0]["id"],"music",music)`;
const newB = `        global_avatar_layout=_load_avatar_layout(connection)${EOL}        for rs, sc in zip(rendered_scenes, scenes):${EOL}            sc_layout_raw = sc["avatar_layout"]${EOL}            try: sc_layout = json.loads(sc_layout_raw) if sc_layout_raw else None${EOL}            except Exception: sc_layout = None${EOL}            rs["avatarLayout"] = _merge_avatar_layout(global_avatar_layout, sc_layout)${EOL}        music["duration_seconds"]=media_duration(music["local_path"]);upsert_asset(connection,run_id,scenes[0]["id"],"music",music)`;
if (!src.includes(oldB)) { console.error('global_layout block miss'); process.exit(1); }
src = src.replace(oldB, newB);

fs.writeFileSync(P, src);
console.log('OK EOL=' + (isCRLF ? 'CRLF' : 'LF'));