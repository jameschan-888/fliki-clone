#!/usr/bin/env node
// Remotion Lambda 协议本地 stub (rev24 stage C #4).
// 端点:
//   POST /renders        -> { jobId, status: 'queued' }
//   GET  /renders/{id}   -> { jobId, status, progress, outputUrl? }
// 提供 /renders/{id}/download 直接 stream 本地 mp4.
// 运行:
//   node scripts/lambda_stub.js [port] [token]
// 默认 5190, token '' 表示不校验。
const http = require("http");
const fs = require("fs");
const path = require("path");
const url = require("url");

const PORT = parseInt(process.argv[2] || "5190", 10);
const TOKEN = process.argv[3] || "";

const OUT_DIR = path.join(__dirname, "..", ".run", "lambda-renders");
fs.mkdirSync(OUT_DIR, { recursive: true });

const jobs = new Map();
let nextId = 1;

function authOk(req) {
  if (!TOKEN) return true;
  return (req.headers["authorization"] || "").replace(/^Bearer\s+/i, "") === TOKEN;
}

function readJson(req) {
  return new Promise((res, rej) => {
    let buf = "";
    req.on("data", c => buf += c);
    req.on("end", () => { try { res(JSON.parse(buf || "{}")); } catch (e) { rej(e); } });
    req.on("error", rej);
  });
}

function writeJson(res, status, body) {
  res.writeHead(status, { "Content-Type": "application/json" });
  res.end(JSON.stringify(body));
}

async function makePlaceholder(outputPath, durSec) {
  const ff = require("child_process").spawn;
  return new Promise((resolve) => {
    const p = ff("ffmpeg", [
      "-y", "-f", "lavfi", "-i", `testsrc=duration=${Math.max(2, durSec)}:size=1280x720:rate=30`,
      "-f", "lavfi", "-i", `sine=frequency=440:duration=${Math.max(2, durSec)}`,
      "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
      "-c:a", "aac", "-shortest", outputPath,
    ], { stdio: "ignore" });
    p.on("exit", (code) => resolve(code === 0));
  });
}

async function handleSubmit(req, res) {
  const body = await readJson(req);
  const id = "lambda-" + Date.now().toString(36) + "-" + nextId++;
  const outPath = path.join(OUT_DIR, id + ".mp4");
  const job = {
    jobId: id,
    status: "queued",
    progress: 0,
    outputPath: outPath,
    outputUrl: null,
    message: "queued",
    durationSec: 0,
    startedAt: Date.now(),
    updatedAt: Date.now(),
  };
  jobs.set(id, job);
  // Decode inputProps if present (base64 of JSON)
  let durSec = 0;
  if (body && body.inputProps) {
    try {
      const props = JSON.parse(Buffer.from(body.inputProps, "base64").toString("utf8"));
      durSec = Number(props.durationInSeconds || 0);
    } catch (e) {}
  }
  job.durationSec = durSec || 5.0;
  // Simulate async progress: queued -> running -> completed
  setTimeout(() => {
    const j = jobs.get(id);
    if (!j) return;
    j.status = "running";
    j.progress = 25;
    j.updatedAt = Date.now();
  }, 800);
  setTimeout(() => {
    const j = jobs.get(id);
    if (!j) return;
    j.status = "running";
    j.progress = 60;
    j.updatedAt = Date.now();
  }, 1800);
  setTimeout(async () => {
    const j = jobs.get(id);
    if (!j) return;
    const ok = await makePlaceholder(j.outputPath, j.durationSec);
    j.status = ok ? "completed" : "failed";
    j.progress = 100;
    j.message = ok ? "rendered" : "ffmpeg failed";
    if (ok) {
      const host = (req.headers["x-forwarded-host"] || req.headers.host || "127.0.0.1:" + PORT);
      j.outputUrl = `http://${host}/renders/${id}/download`;
    }
    j.updatedAt = Date.now();
  }, 3000);
  writeJson(res, 202, { jobId: id, status: "queued" });
}

function handleGet(req, res, id) {
  const job = jobs.get(id);
  if (!job) return writeJson(res, 404, { error: "not_found" });
  writeJson(res, 200, {
    jobId: job.jobId,
    status: job.status,
    progress: job.progress,
    message: job.message,
    outputUrl: job.outputUrl,
    startedAt: new Date(job.startedAt).toISOString(),
    updatedAt: new Date(job.updatedAt).toISOString(),
  });
}

function handleDownload(req, res, id) {
  const job = jobs.get(id);
  if (!job || !job.outputUrl || !fs.existsSync(job.outputPath)) {
    return writeJson(res, 404, { error: "not_ready" });
  }
  res.writeHead(200, {
    "Content-Type": "video/mp4",
    "Content-Length": fs.statSync(job.outputPath).size,
  });
  fs.createReadStream(job.outputPath).pipe(res);
}

function handleHealth(req, res) {
  writeJson(res, 200, { status: "ok", jobs: jobs.size, port: PORT });
}

const server = http.createServer(async (req, res) => {
  if (!authOk(req)) return writeJson(res, 401, { error: "unauthorized" });
  const u = url.parse(req.url, true);
  const m = req.method;
  if (m === "GET" && u.pathname === "/health") return handleHealth(req, res);
  if (m === "POST" && u.pathname === "/renders") return handleSubmit(req, res);
  const m2 = /^\/renders\/([^/]+)(\/download)?$/.exec(u.pathname);
  if (m === "GET" && m2) {
    if (m2[2]) return handleDownload(req, res, m2[1]);
    return handleGet(req, res, m2[1]);
  }
  writeJson(res, 404, { error: "not_found" });
});

server.listen(PORT, "127.0.0.1", () => {
  console.log("[lambda-stub] listening on http://127.0.0.1:" + PORT + " token=" + (TOKEN ? "set" : "off"));
  console.log("[lambda-stub] output dir: " + OUT_DIR);
});
