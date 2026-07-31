// Fliki P6D 一键安装脚本 (Node 实现, 跨 PS 5.1/7+)
// 用法: scripts\\bootstrap.cmd  或  node scripts\\bootstrap.js
const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const BACKEND = path.join(ROOT, 'backend');
const APP = path.join(ROOT, 'app');

function log(msg) { process.stdout.write('[' + new Date().toISOString() + '] ' + msg + '\n'); }
function fail(msg) { log('FATAL: ' + msg); process.exit(1); }

function run(cmd, args, opts) {
  opts = opts || {};
  // .cmd/.bat 必须 shell:true (Windows Node spawnSync 直接调 .cmd 返回 status:null)
  const needShell = /\.(cmd|bat)$/i.test(cmd) || opts.shell;
  log('> ' + cmd + ' ' + args.join(' ') + (needShell ? ' [shell]' : ''));
  const r = spawnSync(cmd, args, Object.assign({ stdio: 'inherit', shell: false }, opts, { shell: needShell }));
  if (r.status !== 0) fail(cmd + ' exit ' + r.status);
  return r;
}

// 0. 前置
run('python', ['-V']);
if (!fs.existsSync(BACKEND)) fail('找不到 backend/ 目录: ' + BACKEND);
if (!fs.existsSync(APP)) fail('找不到 app/ 目录: ' + APP);

// 1. 创建 .venv
const VENV = path.join(BACKEND, '.venv');
const PYBIN = path.join(VENV, process.platform === 'win32' ? 'Scripts\\python.exe' : 'bin/python');
if (!fs.existsSync(VENV)) {
  log('创建 .venv ...');
  run('python', ['-m', 'venv', VENV]);
} else {
  log('.venv 已存在, 跳过创建');
}

// 2. 升级 pip + 安装依赖
log('升级 pip ...');
run(PYBIN, ['-m', 'pip', 'install', '--upgrade', 'pip', '--disable-pip-version-check']);

log('安装 backend/requirements.txt ...');
run(PYBIN, ['-m', 'pip', 'install', '-r', path.join(BACKEND, 'requirements.txt'), '--disable-pip-version-check']);

log('安装 backend/requirements-wav2lip.txt (可选 Wav2Lip 依赖) ...');
const wav2lipOk = run(PYBIN, ['-m', 'pip', 'install', '-r', path.join(BACKEND, 'requirements-wav2lip.txt'), '--disable-pip-version-check']);
if (wav2lipOk.status !== 0) {
  log('WARN: Wav2Lip 依赖安装失败, 不影响主链路 (Script-to-video / Auto-edit 不依赖)');
}

// 3. 拷贝 .env.example -> .env
const envExample = path.join(BACKEND, '.env.example');
const envFile = path.join(BACKEND, '.env');
if (fs.existsSync(envExample) && !fs.existsSync(envFile)) {
  fs.copyFileSync(envExample, envFile);
  log('已生成 backend\\.env (从 .env.example 复制, 请填入真实 key)');
} else if (fs.existsSync(envFile)) {
  log('backend\\.env 已存在, 跳过');
} else {
  log('WARN: 找不到 backend\\.env.example');
}

// 4. 前端 npm install
log('cd app && npm.cmd install ...');
run('npm.cmd', ['install', '--no-audit', '--no-fund'], { cwd: APP, shell: true });

// 5. 自检
log('python -m compileall backend ...');
run(PYBIN, ['-m', 'compileall', '-q', BACKEND]);

log('npm.cmd run build ...');
run('npm.cmd', ['run', 'build'], { cwd: APP, shell: true });

log('==== bootstrap 完成 ====');
log('下一步: scripts\\start_backend.cmd / start_frontend.cmd / status.cmd');
