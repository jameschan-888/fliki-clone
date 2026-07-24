// 启动 headroom proxy 到 8787（detached + 日志 + PID）
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

const EXE = 'C:\\Users\\chanl\\AppData\\Local\\Programs\\Python\\Python312\\Scripts\\headroom.EXE';
const ARGS = [
  'proxy',
  '--host', '127.0.0.1',
  '--port', '8787',
  '--mode', 'cache',
  '--no-telemetry',
  '--workers', '1',
];
const ROOT = 'D:\\workspace\\Fliki视频制作还原';
const RUN = path.join(ROOT, '.run');
fs.mkdirSync(RUN, { recursive: true });
const out = fs.openSync(path.join(RUN, 'headroom-proxy.log'), 'a');
const err = fs.openSync(path.join(RUN, 'headroom-proxy.log.err'), 'a');

const child = spawn(EXE, ARGS, {
  detached: true,
  stdio: ['ignore', out, err],
  windowsHide: true,
  shell: false,
});
fs.writeFileSync(path.join(RUN, 'headroom-proxy.pid'), String(child.pid));
console.log('spawned pid=' + child.pid);
child.unref();