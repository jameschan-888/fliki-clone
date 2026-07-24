#!/usr/bin/env python3
# Auto-generated: 2026-07-25
import os
import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException

import avatar_clone_router


PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC = b"\xff\xd8\xff\xe0"
WEBP_MAGIC = b"RIFF\x00\x00\x00\x00WEBP"


class ImageMagicValidationTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except (PermissionError, OSError):
            pass

    def _write(self, name, ext, content):
        p = self.root / f"{name}{ext}"
        p.write_bytes(content)
        return p

    def test_real_png_passes(self):
        body = PNG_MAGIC + b"\x00" * 1024
        p = self._write("face", ".png", body)
        self.assertEqual(avatar_clone_router._validate_image_magic(p, ".png"), body[:12])

    def test_real_jpeg_passes(self):
        body = JPEG_MAGIC + b"\x00" * 1024
        p = self._write("face", ".jpg", body)
        self.assertEqual(avatar_clone_router._validate_image_magic(p, ".jpg"), body[:12])

    def test_real_webp_passes(self):
        p = self._write("face", ".webp", WEBP_MAGIC + b"\x00" * 100)
        head = avatar_clone_router._validate_image_magic(p, ".webp")
        self.assertTrue(head.startswith(b"RIFF"))

    def test_fake_png_raises_422(self):
        body = b"NOT A PNG" + b"\x00" * 200
        p = self._write("face", ".png", body)
        with self.assertRaises(HTTPException) as ctx:
            avatar_clone_router._validate_image_magic(p, ".png")
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("magic bytes", ctx.exception.detail.lower())

    def test_png_extension_with_jpeg_content_raises(self):
        body = JPEG_MAGIC + b"\x00" * 200
        p = self._write("face", ".png", body)
        with self.assertRaises(HTTPException) as ctx:
            avatar_clone_router._validate_image_magic(p, ".png")
        self.assertEqual(ctx.exception.status_code, 422)

    def test_unknown_extension_passes_through(self):
        body = b"\x00" * 100
        p = self._write("face", ".xyz", body)
        self.assertEqual(avatar_clone_router._validate_image_magic(p, ".xyz"), b"")

    def test_truncated_png_signature_raises_422(self):
        body = PNG_MAGIC[:4] + b"\x00" * 200
        p = self._write("face", ".png", body)
        with self.assertRaises(HTTPException) as ctx:
            avatar_clone_router._validate_image_magic(p, ".png")
        self.assertEqual(ctx.exception.status_code, 422)

    def test_short_file_under_sniff_bytes_still_passes_for_known(self):
        body = b"\xff\xd8\xff"
        p = self._write("face", ".jpg", body)
        self.assertEqual(avatar_clone_router._validate_image_magic(p, ".jpg"), body)

    def test_gif87a_passes(self):
        body = b"GIF87a" + b"\x00" * 50
        p = self._write("face", ".gif", body)
        self.assertTrue(avatar_clone_router._validate_image_magic(p, ".gif").startswith(b"GIF"))

    def test_bmp_passes(self):
        body = b"BM" + b"\x00" * 100
        p = self._write("face", ".bmp", body)
        self.assertTrue(avatar_clone_router._validate_image_magic(p, ".bmp").startswith(b"BM"))
