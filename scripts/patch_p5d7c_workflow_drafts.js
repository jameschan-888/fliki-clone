const fs = require('fs');
const P = 'D:/workspace/Fliki视频制作还原/backend/workflow_drafts.py';
let src = fs.readFileSync(P, 'utf8');
const EOL = src.includes('\r\n') ? '\r\n' : '\n';

// 1) scene_from_row
const oldSfr = `def scene_from_row(row):${EOL}    return {name: row[name] for name in ("id", "position", "title", "narration", "visual_intent", "subtitle", "duration_seconds", "voice", "avatar")}`;
const newSfr = [
  'def scene_from_row(row):',
  '    out = {name: row[name] for name in ("id", "position", "title", "narration", "visual_intent", "subtitle", "duration_seconds", "voice", "avatar")}',
  '    layout = row["avatar_layout"]',
  '    if layout:',
  '        try: out["avatar_layout"] = json.loads(layout)',
  '        except Exception: out["avatar_layout"] = None',
  '    return out',
].join(EOL);
if (!src.includes(oldSfr)) { console.error('scene_from_row pattern miss'); console.error('--- TRY ---'); console.error(JSON.stringify(src.split(EOL).find(l => l.includes('scene_from_row')))); process.exit(1); }
src = src.replace(oldSfr, newSfr);

// 2) update_scene 序列化
const oldUpd = `            values = body.model_dump(exclude_unset=True)${EOL}            assignments = ", ".join(f"{name}=?" for name in values)${EOL}            connection.execute(f"UPDATE scene_drafts SET {assignments}, updated_at=? WHERE id=?", (*values.values(), utc_now(), scene_id))`;
const newUpd = `            values = body.model_dump(exclude_unset=True)${EOL}            if "avatar_layout" in values and values["avatar_layout"] is not None:${EOL}                values["avatar_layout"] = json.dumps(values["avatar_layout"], ensure_ascii=False)${EOL}            assignments = ", ".join(f"{name}=?" for name in values)${EOL}            connection.execute(f"UPDATE scene_drafts SET {assignments}, updated_at=? WHERE id=?", (*values.values(), utc_now(), scene_id))`;
if (!src.includes(oldUpd)) { console.error('update_scene pattern miss'); process.exit(1); }
src = src.replace(oldUpd, newUpd);

fs.writeFileSync(P, src);
console.log('OK');