// P1-5 phase 8 helper: 让 ci.js 自动起后端 + 等就绪 + 跑完不杀 (用户自己起的 5181 复用)
// 复用 start_backend.js 的 spawn 逻辑, 加 wait-for-ready 健康检查
const { spawn, spawnSync } = require('child_process');
const http = require('http');
const path = require('path');
const fs = require('fs');

const ROOT = 'D:\\workspace\\Fliki视频制作还原';
const BACKEND = path.join(ROOT, 'backend');
const RUN = path.join(ROOT, '.run');
const LOG = path.join(RUN, 'backend.ci.log');
const ERR = path.join(RUN, 'backend.ci.log.err');
const PID = path.join(RUN, 'backend.ci.pid');
const HOST = '127.0.0.1';
const PORT = 5181;
const HEALTH = 'http://' + HOST + ':' + PORT + '/health';
const WAIT_TIMEOUT_MS = 30000;

function isListening() {
  if (fs.existsSync(PID)) {
    const pid = parseInt(fs.readFileSync(PID, 'utf8').trim(), 10);
    if (pid) {
      try { process.kill(pid, 0); return true; } catch (e) { fs.unlinkSync(PID); }
    }
  }
  // 端口探测, 区分 ci 自己起的和用户自己起的
  const r = spawnSync('powershell', ['-NoProfile', '-Command',
    'try { (Test-NetConnection -ComputerName 127.0.0.1 -Port 5181 -WarningAction SilentlyContinue -InformationLevel Quiet) } catch { $false }'],
    { encoding: 'utf8' });
  return /True/i.test(r.stdout || '');
}

function startBackend() {
  if (!fs.existsSync(RUN)) fs.mkdirSync(RUN, { recursive: true });
  const out = fs.openSync(LOG, 'a');
  const err = fs.openSync(ERR, 'a');
  const child = spawn('python', ['-m', 'uvicorn', 'main:app', '--host', HOST, '--port', String(PORT)], {
    cwd: BACKEND, detached: true, stdio: ['ignore', out, err], windowsHide: true,
    env: Object.assign({}, process.env, {
      RENDER_PROVIDER: process.env.RENDER_PROVIDER || 'cloud',
      RENDER_SEGMENT_SCENES: process.env.RENDER_SEGMENT_SCENES || '10',
    }),
  });
  fs.writeFileSync(PID, String(child.pid));
  fs.appendFileSync(LOG, '[' + new Date().toISOString() + '] ci spawned pid=' + child.pid + '\n');
  child.unref();
  return child.pid;
}

function waitReady(timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  return new Promise((resolve, reject) => {
    const tick = () => {
      http.get(HEALTH, (res) => {
        if (res.statusCode === 200) { resolve(); return; }
        if (Date.now() > deadline) { reject(new Error('waitReady timeout after ' + timeoutMs + 'ms')); return; }
        setTimeout(tick, 300);
      }).on('error', () => {
        if (Date.now() > deadline) { reject(new Error('waitReady timeout after ' + timeoutMs + 'ms')); return; }
        setTimeout(tick, 300);
      });
    };
    tick();
  });
}

async function ensureBackend() {
  if (isListening()) {
    return { spawned: false, pid: null };
  }
  const pid = startBackend();
  await waitReady(WAIT_TIMEOUT_MS);
  return { spawned: true, pid: pid };
}


function pollReadySync(timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const r = spawnSync('curl', ['-s', '-o', 'NUL', '-w', '%{http_code}', HEALTH], { encoding: 'utf8' });
      if ((r.stdout || '').trim() === '200') return true;
    } catch (e) { /* ignore, retry */ }
    const slept = require('child_process').spawnSync('powershell', ['-NoProfile', '-Command', 'Start-Sleep -Milliseconds 300'], { encoding: 'utf8' });
  }
  return false;
}

function ensureBackendSync() {
  if (isListening()) return { spawned: false, pid: null };
  const pid = startBackend();
  const ok = pollReadySync(WAIT_TIMEOUT_MS);
  if (!ok) {
    throw new Error('backend 启动后 ' + (WAIT_TIMEOUT_MS/1000) + 's 内未就绪 (健康检查 ' + HEALTH + ' 失败)');
  }
  return { spawned: true, pid: pid };
}

module.exports = { ensureBackend, ensureBackendSync, isListening, startBackend, waitReady, HEALTH, PID };
