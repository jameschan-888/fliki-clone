const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

const ROOT = 'D:\\workspace\\Fliki视频制作还原';
const BACKEND = path.join(ROOT, 'backend');
const RUN = path.join(ROOT, '.run');
fs.mkdirSync(RUN, { recursive: true });
const LOG = path.join(RUN, 'backend.log');
const ERR = path.join(RUN, 'backend.log.err');
const PID = path.join(RUN, 'backend.pid');

const out = fs.openSync(LOG, 'a');
const err = fs.openSync(ERR, 'a');
const child = spawn('python', ['-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', '8765'], {
  cwd: BACKEND, detached: true, stdio: ['ignore', out, err], windowsHide: true,
});
fs.writeFileSync(PID, String(child.pid));
fs.appendFileSync(LOG, `\n[${new Date().toISOString()}] spawned pid=${child.pid} port=8765\n`);
console.log('spawned pid=' + child.pid);
child.unref();