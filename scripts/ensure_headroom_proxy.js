// 守护 headroom proxy (8787) 持续在线：发现死掉自动拉起。
// 计划任务版本（user logon trigger）会另写 install-headroom-proxy.ps1。
const { spawn } = require('child_process');
const http = require('http');
const path = require('path');
const fs = require('fs');

const EXE = 'C:\\Users\\chanl\\AppData\\Local\\Programs\\Python\\Python312\\Scripts\\headroom.EXE';
const ROOT = 'D:\\workspace\\Fliki视频制作还原';
const RUN = path.join(ROOT, '.run');
const LOG = path.join(RUN, 'headroom-proxy.log');
const ERR = path.join(RUN, 'headroom-proxy.log.err');
const PID = path.join(RUN, 'headroom-proxy.pid');
const ARGS = ['proxy', '--host', '127.0.0.1', '--port', '8787', '--mode', 'cache', '--no-telemetry', '--workers', '1'];
const PORT = 8787;

fs.mkdirSync(RUN, { recursive: true });
fs.appendFileSync(LOG, `\n[${new Date().toISOString()}] ensure_headroom_proxy started\n`);

function check() {
  return new Promise((resolve) => {
    const req = http.get({ host: '127.0.0.1', port: PORT, path: '/livez', timeout: 1500 }, (res) => {
      res.resume();
      resolve(res.statusCode === 200);
    });
    req.on('error', () => resolve(false));
    req.on('timeout', () => { req.destroy(); resolve(false); });
  });
}

function spawnProxy() {
  const out = fs.openSync(LOG, 'a');
  const err = fs.openSync(ERR, 'a');
  const child = spawn(EXE, ARGS, { detached: true, stdio: ['ignore', out, err], windowsHide: true });
  fs.writeFileSync(PID, String(child.pid));
  fs.appendFileSync(LOG, `[${new Date().toISOString()}] spawned pid=${child.pid}\n`);
  child.unref();
  return child.pid;
}

(async () => {
  if (!(await check())) {
    fs.appendFileSync(LOG, `[${new Date().toISOString()}] proxy not up, spawning\n`);
    spawnProxy();
  } else {
    fs.appendFileSync(LOG, `[${new Date().toISOString()}] proxy already up\n`);
  }
  setInterval(async () => {
    if (!(await check())) {
      fs.appendFileSync(LOG, `[${new Date().toISOString()}] proxy died, respawning\n`);
      spawnProxy();
    }
  }, 30000);
})();