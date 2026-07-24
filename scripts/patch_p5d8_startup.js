const fs = require('fs');
const P = 'D:/workspace/Fliki视频制作还原/backend/main.py';
let src = fs.readFileSync(P, 'utf8');
const CRLF = '\r\n';

const oldSt = '@app.on_event("startup")' + CRLF + "def startup():" + CRLF +
"    if init_db():" + CRLF +
'        print("[database] Added scene_drafts.voice compatibility column")' + CRLF +
"    connection = get_db()" + CRLF +
"    try:" + CRLF +
"        seed_runtime_providers(connection)" + CRLF +
"        ensure_voices(connection)" + CRLF +
"    finally:" + CRLF +
"        connection.close()" + CRLF +
"    write_startup_diagnostic()";

const nwSt = '@app.on_event("startup")' + CRLF + "def startup():" + CRLF +
"    if init_db():" + CRLF +
'        print("[database] Added scene_drafts.voice compatibility column")' + CRLF +
"    connection = get_db()" + CRLF +
"    try:" + CRLF +
"        seed_runtime_providers(connection)" + CRLF +
"        ensure_voices(connection)" + CRLF +
"    finally:" + CRLF +
"        connection.close()" + CRLF +
"    # write_startup_diagnostic 联网探测耗 4-36s；改后台线程避免阻塞 startup" + CRLF +
'    threading.Thread(target=_background_diagnostic, name="env-diagnostic", daemon=True).start()';

if (!src.includes(oldSt)) { console.error('startup miss'); process.exit(1); }
src = src.replace(oldSt, nwSt);

const oldHc = '@app.get("/health")';
const nwHc = '@app.get("/startup-status")' + CRLF + "def startup_status():" + CRLF + "    return _startup_diagnostic_status" + CRLF + CRLF + '@app.get("/health")';
if (!src.includes(oldHc)) { console.error('health miss'); process.exit(1); }
src = src.replace(oldHc, nwHc);

fs.writeFileSync(P, src);
console.log('OK');