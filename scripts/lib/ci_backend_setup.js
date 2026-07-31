// phase 8 setup: 同步确保后端在 5181, 用户自己起的不动, 没起就 spawn
try {
  const { ensureBackendSync } = require('./ci_backend');
  const r = ensureBackendSync();
  console.log('[setup] backend OK, spawned=' + r.spawned + (r.pid ? ' pid=' + r.pid : ''));
  process.exit(0);
} catch (e) {
  console.error('[setup] backend 启动失败:', e.message);
  process.exit(1);
}
