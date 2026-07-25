import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import main
from workflow_pipeline import enrich_voice_with_cadence


class EnrichVoiceWithCadenceTest(unittest.TestCase):
    def test_attaches_segments_and_summary(self):
        fake_path = Path(tempfile.mkdtemp()) / "voice.mp3"
        fake_path.write_bytes(b"MP3")
        tts = {"provider": "edge_tts", "voice": "y", "local_path": str(fake_path), "duration_seconds": 1.0}
        with mock.patch(
            "workflow_pipeline.cadence_detect",
            return_value=[{"start": 0.0, "silence_after": 0.0}, {"start": 1.0, "silence_after": 0.3}],
        ), mock.patch(
            "workflow_pipeline.cadence_summary_svc",
            return_value={"count": 2, "avg_silence": 0.15, "max_silence": 0.3},
        ):
            enrich_voice_with_cadence(tts)
        self.assertEqual(len(tts["cadence_segments"]), 2)
        self.assertEqual(tts["cadence_summary"]["count"], 2)

    def test_missing_audio_path_uses_zero_summary(self):
        tts = {"provider": "edge_tts", "voice": "y"}
        enrich_voice_with_cadence(tts)
        self.assertEqual(tts["cadence_segments"], [])
        self.assertEqual(tts["cadence_summary"]["count"], 0)

    def test_detect_failure_does_not_break_tts(self):
        fake_path = Path(tempfile.mkdtemp()) / "voice.mp3"
        fake_path.write_bytes(b"MP3")
        tts = {"provider": "edge_tts", "voice": "y", "local_path": str(fake_path)}
        with unittest.mock.patch("workflow_pipeline.cadence_detect", side_effect=RuntimeError("boom")):
            enrich_voice_with_cadence(tts)
        self.assertEqual(tts["cadence_segments"], [])
        self.assertEqual(tts["cadence_summary"]["count"], 0)


if __name__ == "__main__":
    import unittest as _u
    _u.main()
