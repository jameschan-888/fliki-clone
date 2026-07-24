const fs = require('fs');
const P = 'D:/workspace/Fliki视频制作还原/backend/db/schema.sql';
const raw = fs.readFileSync(P);
const EOL = raw.includes(Buffer.from([13, 10])) ? '\r\n' : '\n';
let src = raw.toString('utf8');

const oldRow = `  avatar TEXT,${EOL}  created_at TEXT NOT NULL,${EOL}  updated_at TEXT NOT NULL`;
const newRow = `  avatar TEXT,${EOL}  avatar_layout TEXT,${EOL}  created_at TEXT NOT NULL,${EOL}  updated_at TEXT NOT NULL`;
if (!src.includes(oldRow)) { console.error('schema row miss'); process.exit(1); }
src = src.replace(oldRow, newRow);
fs.writeFileSync(P, src);
console.log('OK');