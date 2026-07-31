import os
import tempfile
import unittest
from pathlib import Path

from file_security import (
    is_within_directory,
    safe_extension,
    safe_filename,
    safe_join,
    validate_not_reserved,
)


class SafeFilenameTest(unittest.TestCase):
    def test_basic_filename_kept(self):
        self.assertEqual(safe_filename("video.mp4"), "video.mp4")

    def test_strips_path_separators(self):
        # 路径分隔符应被裁掉 (只保留 basename)
        self.assertEqual(safe_filename("../../../etc/passwd"), "passwd")
        self.assertEqual(safe_filename("..\\..\\windows\\system32\\cmd.exe"), "cmd.exe")

    def test_strips_windows_forbidden_chars(self):
        # < > : " / \ | ? * 全部替换为 _
        self.assertNotIn("/", safe_filename("foo/bar.mp4"))
        self.assertNotIn("\\", safe_filename("foo\\bar.mp4"))
        # \\ 是 Python 转义后的 \, 实际传入的是单个反斜杠
        cleaned = safe_filename("foo<bar>:baz?.mp4")
        for ch in '<>:"|?*':
            self.assertNotIn(ch, cleaned)

    def test_rejects_windows_reserved_names(self):
        # CON.txt 应自动加前缀绕过保留名 (而不是直接报错)
        self.assertEqual(safe_filename("CON.txt"), "_CON.txt")
        self.assertEqual(safe_filename("PRN"), "_PRN")
        self.assertEqual(safe_filename("com1.log"), "_com1.log")
        # 大小写不敏感
        self.assertEqual(safe_filename("aux.txt"), "_aux.txt")

    def test_strips_diacritics(self):
        # 重音符号应去除 (NFKD 折叠)
        # café -> cafe
        result = safe_filename("café.mp4")
        self.assertIn("cafe", result)

    def test_fallback_for_empty(self):
        self.assertEqual(safe_filename(""), "file")
        self.assertEqual(safe_filename("   "), "file")
        self.assertEqual(safe_filename("////"), "file")
        self.assertEqual(safe_filename('<>:"|?*'), "file")

    def test_length_truncation(self):
        # 超过 max_length 应截断
        long = "a" * 200 + ".mp4"
        result = safe_filename(long, max_length=120)
        self.assertLessEqual(len(result), 120)
        # 扩展名应保留
        self.assertTrue(result.endswith(".mp4"))

    def test_strip_leading_trailing_dots(self):
        # 文件名不应以 . 或 - 开头 (Windows 兼容)
        self.assertFalse(safe_filename("..hidden").startswith("."))
        self.assertFalse(safe_filename("-leading").startswith("-"))


class ValidateNotReservedTest(unittest.TestCase):
    def test_reserved_names_raise(self):
        for name in ["CON", "PRN", "AUX", "NUL", "COM1", "LPT9", "con.txt", "AUX.log"]:
            with self.assertRaises(ValueError):
                validate_not_reserved(name)

    def test_normal_names_pass(self):
        for name in ["video.mp4", "report.docx", "data.json", "image.png"]:
            validate_not_reserved(name)  # should not raise


class SafeJoinTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_simple_join_within_base(self):
        result = safe_join(self.tmp, "subdir", "file.mp4")
        self.assertTrue(is_within_directory(result, self.tmp))

    def test_path_traversal_blocked(self):
        with self.assertRaises(ValueError):
            safe_join(self.tmp, "..", "..", "etc", "passwd")

    def test_absolute_path_escape_blocked(self):
        # 用户传绝对路径试图跳出 base
        with self.assertRaises(ValueError):
            safe_join(self.tmp, "C:\\Windows\\System32")

    def test_nested_directory(self):
        nested = safe_join(self.tmp, "a", "b", "c", "deep.mp4")
        self.assertEqual(nested.parent.name, "c")


class SafeExtensionTest(unittest.TestCase):
    def test_valid_extensions(self):
        self.assertEqual(safe_extension("video.mp4", [".mp4", ".mov"]), ".mp4")
        self.assertEqual(safe_extension("VIDEO.MP4", [".mp4"]), ".mp4")

    def test_invalid_extension_raises(self):
        with self.assertRaises(ValueError):
            safe_extension("video.exe", [".mp4", ".mov"])

    def test_no_extension_raises(self):
        with self.assertRaises(ValueError):
            safe_extension("video", [".mp4"])


class IsWithinDirectoryTest(unittest.TestCase):
    def test_inside_returns_true(self):
        with tempfile.TemporaryDirectory() as base:
            inside = Path(base) / "sub" / "file.mp4"
            inside.parent.mkdir(parents=True, exist_ok=True)
            self.assertTrue(is_within_directory(inside, base))

    def test_outside_returns_false(self):
        with tempfile.TemporaryDirectory() as base:
            self.assertFalse(is_within_directory(Path(base).parent, base))


if __name__ == "__main__":
    unittest.main()
