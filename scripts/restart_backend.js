const { spawn, execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const ROOT = 'D:/workspace/Fliki视频制作还原';
const PID = path.join(ROOT, '.run', 'backend.pid');
const LOG = path.join(ROOT, '.run', 'backend.log');
const ERR = path.join(ROOT, '.run', 'backend.log.err');
const PORT = 5181;

try {
  if (fs.existsSync(PID)) {
    const pid = parseInt(fs.readFileSync(PID, 'utf8').trim(), 10);
    if (pid) {
      try { process.kill(pid, 'SIGTERM'); console.log('SIGTERM', pid); } catch {}
      try { execSync(`taskkill /F /PID ${pid} /T`, { stdio: 'ignore' }); } catch {}
    }
  }
  execSync(`powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort ${PORT} -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id \\$_.OwningProcess -Force -ErrorAction SilentlyContinue }"`, { stdio: 'ignore' });
} catch (e) { console.log('kill err', e.message); }

fs.mkdirSync(path.join(ROOT, '.run'), { recursive: true });
const out = fs.openSync(LOG, 'a');
const er = fs.openSync(ERR, 'a');
fs.appendFileSync(LOG, `\n[${new Date().toISOString()}] restart spawned\n`);
const child = spawn('python', ['-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', String(PORT)], {
  cwd: path.join(ROOT, 'backend'),
  detached: true,
  stdio: ['ignore', out, er],
  windowsHide: true,
});
fs.writeFileSync(PID, String(child.pid));
console.log('spawned pid=' + child.pid);
child.unref();