// 通过 stdio 与 headroom mcp 通讯：init + tools/list + 调用 headroom_stats
const { spawn } = require('child_process');
const path = require('path');

const EXE = 'C:\\Users\\chanl\\AppData\\Local\\Programs\\Python\\Python312\\Scripts\\headroom.EXE';
const child = spawn(EXE, ['mcp', 'serve'], { stdio: ['pipe', 'pipe', 'pipe'], windowsHide: true });
let buf = '';
let idCounter = 0;
const pending = new Map();
function send(method, params) {
  const id = ++idCounter;
  const msg = { jsonrpc: '2.0', id, method, params };
  child.stdin.write(JSON.stringify(msg) + '\n');
  return id;
}
child.stdout.on('data', (chunk) => {
  buf += chunk.toString('utf8');
  let idx;
  while ((idx = buf.indexOf('\n')) !== -1) {
    const line = buf.slice(0, idx); buf = buf.slice(idx + 1);
    if (!line.trim()) continue;
    try {
      const m = JSON.parse(line);
      if (m.id && pending.has(m.id)) { const r = pending.get(m.id); pending.delete(m.id); r(m); }
      else if (m.id) console.log('UNSOLICITED:', JSON.stringify(m).slice(0, 200));
    } catch (e) { console.log('PARSE_ERR:', e.message, line.slice(0, 100)); }
  }
});
child.stderr.on('data', (c) => process.stderr.write(c));
child.on('exit', (code) => { console.log('CHILD_EXIT', code); process.exit(code || 0); });

function call(method, params) {
  return new Promise((resolve) => {
    const id = send(method, params);
    pending.set(id, resolve);
  });
}

(async () => {
  await call('initialize', { protocolVersion: '2024-11-05', capabilities: {}, clientInfo: { name: 'smoke', version: '0' } });
  child.stdin.write(JSON.stringify({ jsonrpc: '2.0', method: 'notifications/initialized' }) + '\n');
  const tools = await call('tools/list', {});
  console.log('TOOLS:', tools.result.tools.map((t) => t.name).join(','));
  const stats = await call('tools/call', { name: 'headroom_stats', arguments: {} });
  console.log('STATS:', JSON.stringify(stats).slice(0, 400));
  const comp = await call('tools/call', { name: 'headroom_compress', arguments: { content: 'line1\nline2\nline3 hello world ' + 'x'.repeat(200) } });
  console.log('COMPRESS:', JSON.stringify(comp).slice(0, 400));
  setTimeout(() => { child.kill(); process.exit(0); }, 1000);
})();