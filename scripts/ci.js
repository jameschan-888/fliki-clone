const { spawnSync } = require("child_process");
const path = require("path");

const ROOT = "D:\\workspace\\Fliki视频制作还原";
process.chdir(ROOT);

const argumentsList = process.argv.slice(2);
const allowedArguments = new Set(["--full", "--offline", "--online", "--list"]);
const unknownArguments = argumentsList.filter((argument) => !allowedArguments.has(argument));
const modeFlags = argumentsList.filter((argument) => argument === "--full" || argument === "--offline" || argument === "--online");
if (unknownArguments.length || modeFlags.length > 1) {
  console.error("Usage: node scripts/ci.js [--full|--offline|--online] [--list]");
  if (unknownArguments.length) console.error("Unknown arguments:", unknownArguments.join(", "));
  process.exit(2);
}
const mode = modeFlags.length ? modeFlags[0].slice(2) : "full";
const listOnly = argumentsList.includes("--list");

// 在 Windows 上, npm/npx/.cmd 必须走 cmd.exe, python.exe 直接 spawn
function run(cmd, args, cwd, timeoutMs, extraEnv) {
  const isWin = process.platform === "win32";
  const needsShell = isWin && (cmd === "npm" || cmd === "npx" || cmd.endsWith(".cmd") || cmd.endsWith(".bat"));
  return spawnSync(cmd, args, {
    cwd,
    shell: needsShell,
    stdio: "inherit",
    timeout: timeoutMs || 600_000,
    env: extraEnv ? { ...process.env, ...extraEnv } : process.env,
  });
}

const allPhases = [
  {
    name: "路由挂载检查 (check_routes.py)",
    cmd: "python",
    args: ["scripts/check_routes.py", "--fail-on-warn"],
    cwd: ROOT,
    allowFail: false,
  },
  {
    name: "后端单元测试 (全量)",
    cmd: "python",
    args: ["-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"],
    cwd: path.join(ROOT, "backend"),
    allowFail: false,
  },
  {
    name: "API 合约测试",
    cmd: "python",
    args: ["-m", "unittest", "tests.test_api_contract"],
    cwd: path.join(ROOT, "backend"),
    allowFail: false,
  },
  {
    name: "Provider 联调测试 (联网)",
    cmd: "python",
    args: ["-m", "unittest", "tests.providers.test_real_provider_matrix"],
    cwd: path.join(ROOT, "backend"),
    kind: "network",
    timeoutMs: 300_000,
    allowFail: true,
  },
  {
    name: "Remotion TS 编译",
    cmd: "node",
    args: ["backend/workers/remotion-project/node_modules/typescript/bin/tsc", "--noEmit", "-p", "backend/workers/remotion-project"],
    cwd: ROOT,
    allowFail: false,
  },
  {
    name: "前端生产构建",
    cmd: "npm",
    args: ["run", "build"],
    cwd: path.join(ROOT, "app"),
    allowFail: false,
  },  {
    name: "前端 vitest (RTL 组件测试)",
    cmd: "npm",
    args: ["test"],
    cwd: path.join(ROOT, "app"),
    allowFail: false,
  },
  {
    // P1-5 + ROI-2 强 gate: 同步起后端 + 秒级模板预览 smoke, 镜像 GitHub CI 顺序.
    // setup 脚本 ensureBackendSync: 用户自己起的 5181 复用, 没起就 spawn + 等就绪.
    name: "模板预览 smoke (强 gate, 缺后端自动起, 30s 内未就绪则 FAIL)",
    cmd: "python",
    args: ["tests/e2e/test_template_preview_smoke.py"],
    cwd: ROOT,
    setup: "scripts/lib/ci_backend_setup.js",
    allowFail: false,
  },
  {
    // P1-3: 像素级视觉回归. 阈值 0.1% (用户最新要求). 复用前端 build 产物. 
    name: "前端视觉回归 (visual_diff)",
    cmd: "python",
    args: ["tests/e2e/visual_diff.py", "--threshold", "0.001"],
    cwd: ROOT,
    setup: "scripts/lib/build_dist_if_needed.js",
    allowFail: false,
  }
];

const phases = mode === "offline"
  ? allPhases.filter((phase) => phase.kind !== "network")
  : mode === "online"
    ? allPhases.filter((phase) => phase.kind === "network")
    : allPhases;

function effectiveAllowFail(phase) {
  return Boolean(phase.allowFail && mode === "full");
}

function phaseEnvironment(phase) {
  if (phase.kind === "network" && mode === "online") {
    return { FLIKI_PROVIDER_MATRIX_STRICT: "1" };
  }
  return undefined;
}

if (listOnly) {
  console.log("[ci] mode=" + mode + " phases=" + phases.length);
  phases.forEach((phase, index) => {
    const kind = phase.kind || "local";
    const timeoutSeconds = Math.round((phase.timeoutMs || 600_000) / 1000);
    console.log((index + 1) + ". [" + kind + "] strict=" + (!effectiveAllowFail(phase)) + " timeout=" + timeoutSeconds + "s " + phase.name);
  });
  process.exit(0);
}

console.log("[ci] mode=" + mode + " phases=" + phases.length);

function runSetup(setupPath, cwd, timeoutMs) {
  if (!setupPath) return { status: 0 };
  return spawnSync('node', [setupPath], { cwd, stdio: 'inherit', timeout: timeoutMs || 60_000 });
}

const startTime = Date.now();
const results = [];
for (const phase of phases) {
  const t0 = Date.now();
  console.log(`\n=== [${results.length + 1}/${phases.length}] ${phase.name} ===`);

  if (phase.setup) {
    const setupResult = runSetup(phase.setup, phase.cwd || ROOT, 60_000);
    if (setupResult.status !== 0) {
      const elapsed = ((Date.now() - t0) / 1000).toFixed(1);
      if (setupResult.error) console.error("[SETUP ERR]", setupResult.error.message);
      console.error("[SETUP FAIL]", phase.setup);
      results.push({ name: phase.name, passed: false, elapsed, allowFail: effectiveAllowFail(phase) });
      console.log(`[${elapsed}s] FAIL - ${phase.name} (setup)`);
      continue;
    }
  }

  const result = run(phase.cmd, phase.args, phase.cwd, phase.timeoutMs || 600_000, phaseEnvironment(phase));
  const elapsed = ((Date.now() - t0) / 1000).toFixed(1);
  const passed = result.status === 0;
  if (!passed) {
    if (result.error) console.error("[ERR]", result.error.message);
    if (result.stderr) console.error("[STDERR]", String(result.stderr).slice(0, 500));
  }
  results.push({ name: phase.name, passed, elapsed, allowFail: effectiveAllowFail(phase) });
  console.log(`[${elapsed}s] ${passed ? "OK" : "FAIL"} - ${phase.name}`);
}

console.log("\n=== 汇总 ===");
let allOk = true;
for (const r of results) {
  const expected = r.passed || r.allowFail;
  const tag = r.passed ? "OK" : (r.allowFail ? "OK (allowed fail)" : "FAIL");
  console.log(`  ${tag.padEnd(20)} ${r.elapsed}s  ${r.name}`);
  if (!expected) allOk = false;
}
const totalElapsed = ((Date.now() - startTime) / 1000).toFixed(1);
console.log(`\n模式: ${mode}  总耗时: ${totalElapsed}s`);
process.exit(allOk ? 0 : 1);
