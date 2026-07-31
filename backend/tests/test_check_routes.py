"""scripts/check_routes.py strict warning gate tests."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check_routes.py"


class CheckRoutesScriptTest(unittest.TestCase):
    def run_gate(self, root: Path, *extra_args: str):
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(root), *extra_args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
            check=False,
        )

    def test_route_gate_script_is_not_gitignored(self):
        result = subprocess.run(
            ["git", "check-ignore", "scripts/check_routes.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertNotEqual(result.returncode, 0, result.stdout)

    def test_ci_invokes_route_gate_in_strict_mode(self):
        ci_source = (ROOT / "scripts" / "ci.js").read_text(encoding="utf-8")
        self.assertIn('args: ["scripts/check_routes.py", "--fail-on-warn"]', ci_source)

    def test_ci_runs_template_preview_smoke_before_full_render(self):
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        preview_command = "python tests/e2e/test_template_preview_smoke.py"
        full_command = "python tests/e2e/test_template_render_e2e.py"
        self.assertIn(preview_command, workflow)
        self.assertIn(full_command, workflow)
        self.assertLess(workflow.index(preview_command), workflow.index(full_command))

    def test_current_project_strict_gate_covers_provider_config(self):
        result = self.run_gate(ROOT, "--fail-on-warn")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("provider_config", result.stdout)
        self.assertIn("warnings: 0", result.stdout)

    def test_unrecognized_router_style_warns_and_strict_mode_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            backend = root / "backend"
            backend.mkdir()
            (backend / "main.py").write_text("from odd_router import build_router\n", encoding="utf-8")
            (backend / "odd_router.py").write_text(
                "from fastapi import APIRouter\n"
                "def build_router():\n"
                "    return APIRouter(prefix='/odd')\n",
                encoding="utf-8",
            )

            relaxed = self.run_gate(root)
            strict = self.run_gate(root, "--fail-on-warn")

        self.assertEqual(relaxed.returncode, 0, relaxed.stdout + relaxed.stderr)
        self.assertIn("UNRECOGNIZED_ROUTER_STYLE", relaxed.stdout)
        self.assertEqual(strict.returncode, 1, strict.stdout + strict.stderr)
        self.assertIn("UNRECOGNIZED_ROUTER_STYLE", strict.stdout)

    def test_missing_mount_fails_without_strict_mode(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            backend = root / "backend"
            backend.mkdir()
            (backend / "main.py").write_text(
                "from demo_router import create_router as create_demo_router\n",
                encoding="utf-8",
            )
            (backend / "demo_router.py").write_text(
                "from fastapi import APIRouter\n"
                "def create_router():\n"
                "    return APIRouter(prefix='/demo')\n",
                encoding="utf-8",
            )
            result = self.run_gate(root)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("INCLUDE_MISSING", result.stdout)


if __name__ == "__main__":
    unittest.main()
