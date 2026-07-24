const fs = require('fs');
const P = 'D:/workspace/Fliki视频制作还原/backend/main.py';
let src = fs.readFileSync(P, 'utf8');
const EOL = src.includes('\r\n') ? '\r\n' : '\n';
const oldM = `        if columns and "avatar" not in columns:${EOL}            conn.execute("ALTER TABLE scene_drafts ADD COLUMN avatar TEXT")${EOL}            migrated = True`;
const newM = `        if columns and "avatar" not in columns:${EOL}            conn.execute("ALTER TABLE scene_drafts ADD COLUMN avatar TEXT")${EOL}            migrated = True${EOL}        if columns and "avatar_layout" not in columns:${EOL}            conn.execute("ALTER TABLE scene_drafts ADD COLUMN avatar_layout TEXT")${EOL}            migrated = True`;
if (!src.includes(oldM)) { console.error('migration pattern miss'); process.exit(1); }
src = src.replace(oldM, newM);
fs.writeFileSync(P, src);
console.log('OK');