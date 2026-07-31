import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from avatar_segment_pipeline import build_segments, synthesize_segmented_avatar


class AvatarSegmentPipelineTest(unittest.TestCase):
    def test_segments_stay_between_two_and_six_seconds(self):
        segments = build_segments(14.0)
        self.assertAlmostEqual(sum(length for _, length in segments), 14.0, places=5)
        self.assertTrue(all(2.0 <= length <= 6.0 for _, length in segments))

    def test_short_audio_is_one_segment(self):
        self.assertEqual(build_segments(1.5), [(0.0, 1.5)])

    def test_cache_reuses_existing_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            face = root / 'face.jpg'; face.write_bytes(b'face')
            audio = root / 'audio.wav'; audio.write_bytes(b'audio')
            output = root / 'out.mp4'
            cached = root / 'cache'
            provider_calls = []
            class FakeProvider:
                def synthesize(self, face_image_path, audio_path, destination_path):
                    provider_calls.append(Path(audio_path).name)
                    Path(destination_path).write_bytes(b'v' * 2048)
                    return {'mode': 'wav2lip_onnx', 'fallback_used': False, 'elapsed_seconds': 1}
            def fake_probe(path, ffprobe_binary='ffprobe'):
                return 7.0
            with patch('avatar_segment_pipeline.probe_duration', fake_probe), patch('avatar_segment_pipeline._run') as run:
                run.side_effect = lambda command, timeout: Path(command[-1]).write_bytes((b'v' * 2048) if command[-1].endswith('.mp4') else b'part')
                result = synthesize_segmented_avatar(face, audio, output, FakeProvider, cache_dir=cached)
                first_count = len(provider_calls)
                output.unlink()
                result2 = synthesize_segmented_avatar(face, audio, output, FakeProvider, cache_dir=cached)
            self.assertEqual(first_count, 2)
            self.assertEqual(len(provider_calls), first_count)
            self.assertFalse(result['cache_hit'])
            self.assertTrue(result2['cache_hit'])


if __name__ == '__main__':
    unittest.main()
