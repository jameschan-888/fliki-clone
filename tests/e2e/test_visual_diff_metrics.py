"""diff_metrics() 单测 — 守住 N41 SSIM 升级不退化."""
import importlib.util
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
VD = ROOT / "tests" / "e2e" / "visual_diff_fliki.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("vd", VD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def vd():
    return _load_module()


def _png(path: Path, w=160, h=120, color=(255, 0, 0)):
    Image.new("RGB", (w, h), color).save(path)
    return path


def test_self_vs_self_ssim_is_one(vd, tmp_path):
    p = _png(tmp_path / "self.png")
    m = vd.diff_metrics(p, p)
    assert m["ok"] is True
    assert m["same_size"] is True
    assert m["pixel_thr8"] == 0.0
    assert m["pixel_thr32"] == 0.0
    assert m["ssim"] == 1.0


def test_different_color_runs_metrics(vd, tmp_path):
    a = _png(tmp_path / "a.png", color=(255, 0, 0))
    b = _png(tmp_path / "b.png", color=(0, 0, 255))
    m = vd.diff_metrics(a, b)
    assert m["ok"] is True
    assert m["pixel_thr8"] > 0.9, f"纯色两张应几乎全 diff, got {m}"
    assert 0.0 <= m["ssim"] < 1.0, f"SSIM 应 < 1, got {m}"


def test_missing_file_returns_ok_false(vd, tmp_path):
    a = _png(tmp_path / "a.png")
    missing = tmp_path / "nope.png"
    m = vd.diff_metrics(a, missing)
    assert m == {"ok": False}


def test_legacy_diff_ratio_still_works(vd, tmp_path):
    a = _png(tmp_path / "a.png", color=(10, 20, 30))
    b = _png(tmp_path / "b.png", color=(200, 100, 50))
    r = vd.diff_ratio(a, b)
    assert r > 0.5, f"legacy diff_ratio 应大于 0.5, got {r}"
    assert r <= 1.0


def test_size_mismatch_is_resized(vd, tmp_path):
    a = _png(tmp_path / "a.png", w=200, h=200)
    b = _png(tmp_path / "b.png", w=400, h=300, color=(0, 255, 0))
    m = vd.diff_metrics(a, b)
    assert m["ok"] is True
    assert m["same_size"] is False
    assert m["ssim"] is not None
