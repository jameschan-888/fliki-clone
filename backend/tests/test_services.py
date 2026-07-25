import os
import shutil
import struct
import subprocess
import tempfile
import unittest
import wave
from pathlib import Path

from services.cadence import (
    cadence_summary,
    detect_voice_segments,
    suggest_scene_end,
    CadenceError,
)
from services.subtitle import align_to_duration, chunk_subtitle
from services.text_layout import break_text, estimate_max_chars


class TextLayoutTest(unittest.TestCase):
    def test_short_text_no_truncation(self):
        lines, warnings = break_text("你好世界", max_chars=18, max_lines=2)
        self.assertEqual(lines, ["你好世界"])
        self.assertEqual(warnings, [])

    def test_mixed_cjk_and_latin_split_by_word(self):
        lines, warnings = break_text("Hello World 你好", max_chars=10, max_lines=2)
        self.assertEqual(warnings, [])
        self.assertGreaterEqual(len(lines), 2)
        # Latin 单词应保持完整
        joined = "".join(lines)
        self.assertIn("Hello", joined)
        self.assertIn("World", joined)
        self.assertIn("你好", joined)

    def test_max_lines_enforced_and_warns(self):
        long = "这是一段非常非常非常长的中文内容用来测试断行器会不会按行截断"
        lines, warnings = break_text(long, max_chars=8, max_lines=2)
        self.assertEqual(len(lines), 2)
        self.assertIn("TEXT_TRUNCATED", warnings)

    def test_estimate_max_chars_rounds_up(self):
        self.assertEqual(estimate_max_chars(15, max_lines=2), 8)
        self.assertEqual(estimate_max_chars(0, max_lines=2), 1)


class SubtitleTest(unittest.TestCase):
    def test_short_text_single_chunk(self):
        self.assertEqual(chunk_subtitle("你好"), ["你好"])

    def test_long_text_splits_on_separator(self):
        chunks = chunk_subtitle("第一句，第二句，第三句，第四句", max_chars=6)
        self.assertGreater(len(chunks), 1)
        joined = "".join(chunks)
        self.assertEqual(joined.replace(" ", ""), "第一句，第二句，第三句，第四句")

    def test_align_to_duration_divides_evenly(self):
        cues = align_to_duration("第一句第二句第三句", duration=6.0, max_chars=4)
        self.assertEqual(len(cues), 3)
        self.assertEqual(cues[0]["start"], 0.0)
        self.assertEqual(cues[-1]["end"], 6.0)

    def test_align_to_duration_zero_returns_empty(self):
        self.assertEqual(align_to_duration("anything", duration=0), [])


class CadenceTest(unittest.TestCase):
    def _make_wav_with_silences(self, td: str) -> Path:
        path = Path(td) / "tone.wav"
        sample_rate = 16000
        duration = 1.5
        silence_then_tone = 0.3
        n_silence = int(sample_rate * silence_then_tone)
        n_tone = int(sample_rate * (duration - silence_then_tone))
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(b"\x00\x00" * n_silence)
            tone = bytearray()
            for i in range(n_tone):
                amplitude = 8000
                sample = int(amplitude * (1 if i % 50 < 25 else -1))
                tone += struct.pack("<h", sample)
            wf.writeframes(bytes(tone))
        return path

    def test_detect_segments_on_real_audio(self):
        if not shutil.which("ffmpeg"):
            self.skipTest("ffmpeg 不在 PATH")
        with tempfile.TemporaryDirectory() as td:
            wav = self._make_wav_with_silences(td)
            segments = detect_voice_segments(wav, noise_db="-20dB", min_duration=0.2)
            self.assertGreater(len(segments), 1)
            self.assertEqual(segments[0]["start"], 0.0)

    def test_detect_raises_for_missing_file(self):
        with self.assertRaises(CadenceError):
            detect_voice_segments(Path(r"D:\this\path\does\not\exist.mp3"))

    def test_suggest_scene_end_is_strictly_after_start(self):
        self.assertGreater(suggest_scene_end(2.0), 2.0)

    def test_summary_on_empty_returns_zeros(self):
        summary = cadence_summary([])
        self.assertEqual(summary["count"], 0)


if __name__ == "__main__":
    unittest.main()
