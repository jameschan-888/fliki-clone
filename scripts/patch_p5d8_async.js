const fs = require('fs');
const P = 'D:/workspace/Fliki视频制作还原/backend/main.py';
let src = fs.readFileSync(P, 'utf8');
const CRLF = '\r\n';

// 直接重写 write_startup_diagnostic 区块：从 def 到下一个 # ===== 之前
const lines = src.split(CRLF);
let s = -1, e = -1;
for (let i = 0; i < lines.length; i++) {
  if (s < 0 && lines[i].indexOf('def write_startup_diagnostic') === 0) s = i;
  if (s >= 0 && e < 0 && i > s && lines[i].indexOf('# =====') === 0) { e = i; break; }
}
if (s < 0 || e < 0) { console.error('anchors miss', s, e); process.exit(1); }
const replacement = [
  '_startup_diagnostic_status = {"state": "pending", "finished_at": None, "error": None}',
  '',
  'def _background_diagnostic():',
  '    try:',
  '        report = write_startup_diagnostic()',
  '        _startup_diagnostic_status["state"] = "ready" if not (report or {}).get("error") else "error"',
  '        _startup_diagnostic_status["error"] = (report or {}).get("error")',
  '    except Exception as error:',
  '        _startup_diagnostic_status["state"] = "error"',
  '        _startup_diagnostic_status["error"] = str(error)',
  '    finally:',
  '        _startup_diagnostic_status["finished_at"] = int(time.time())',
  '',
  'def write_startup_diagnostic():',
  '    try:',
  '        report = run_full_diagnostic()',
  '        report_path = Path(config["DATA_DIR"]) / "env-check.json"',
  '        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")',
  '        for warning in report.get("warnings", []):',
  "            print(f\"[env-check] {warning.get('level', 'info').upper()}: {warning.get('msg', '')}\")",
  '        return report',
  '    except Exception as error:',
  '        print(f"[env-check] WARNING: startup diagnostic failed: {error}")',
  '        return {"error": str(error)}',
];
const out = lines.slice(0, s).concat(replacement).concat(lines.slice(e));
fs.writeFileSync(P, out.join(CRLF));
console.log('OK replaced lines', s, '-', e - 1, 'with', replacement.length, 'lines');