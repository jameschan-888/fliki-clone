// 检查 app/dist 是否存在 (且比 src 新). 不存在或太旧就跑 npm run build.
// 任何 phase 的 setup 钩子, exit code != 0 会让 phase FAIL.
const fs = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const ROOT = path.resolve(__dirname, "..", "..");
const APP = path.join(ROOT, "app");
const DIST = path.join(APP, "dist", "index.html");
const SRC_INDEX = path.join(APP, "src", "App.tsx");

function exists(p) { try { return fs.statSync(p); } catch { return null; } }

const distStat = exists(DIST);
const srcStat = exists(SRC_INDEX);

let needsBuild = false;
if (!distStat) {
  console.log("[build_dist_if_needed] dist/index.html missing -> build");
  needsBuild = true;
} else if (srcStat && srcStat.mtimeMs > distStat.mtimeMs) {
  console.log("[build_dist_if_needed] src newer than dist -> rebuild");
  needsBuild = true;
} else {
  console.log("[build_dist_if_needed] dist up-to-date -> skip build");
}

if (needsBuild) {
  const result = spawnSync("npm", ["run", "build"], { cwd: APP, shell: true, stdio: "inherit", timeout: 300_000 });
  process.exit(result.status || 0);
} else {
  process.exit(0);
}
