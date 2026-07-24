// Auto-generated: 2026-07-25 (rev3 final)
const { spawnSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const BACKEND = 'D:/workspace/Fliki视频制作还原/backend';
const LOG_DIR = 'D:/workspace/Fliki视频制作还原/.run';

function parseArgs() {
  const args = process.argv.slice(2);
  const opts = { modules: [], timeout: 180000 };
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--modules') {
      opts.modules = args[++i].split(',').map(s => s.trim().replace(/\.py$/, ''));
    } else if (args[i] === '--timeout') {
      opts.timeout = parseInt(args[++i], 10);
    }
  }
  return opts;
}

const opts = parseArgs();
const ts = new Date().toISOString().replace(/[:.]/g, '-');

if (opts.modules.length === 0) {
  console.error('usage: node run_tests.js --modules test_workflow_drafts,test_characters [--timeout 60000]');
  process.exit(2);
}

console.log('[run_tests] backend:', BACKEND);
console.log('[run_tests] modules:', opts.modules.length, 'timeout:', opts.timeout);
opts.modules.forEach(m => console.log('  - tests.' + m));

const args = ['-u', '-m', 'unittest', '-v', ...opts.modules.map(m => 'tests.' + m)];

const result = spawnSync('python', args, {
  cwd: BACKEND,
  encoding: 'utf8',
  timeout: opts.timeout,
  maxBuffer: 64 * 1024 * 1024,
  env: { ...process.env, PYTHONIOENCODING: 'utf-8', PYTHONUTF8: '1' }
});

const logPath = path.join(LOG_DIR, 'test_run_' + ts + '.log');
fs.writeFileSync(logPath, (result.stdout || '') + (result.stderr || ''), 'utf8');

console.log('\n[run_tests] status:', result.status, 'signal:', result.signal, 'timedOut:', !!result.error);
console.log('[run_tests] log:', logPath);

const lines = (result.stdout || '').split(/\r?\n/);
const tail = lines.slice(-30).join('\n');
console.log('\n--- LAST 30 LINES ---');
console.log(tail);
