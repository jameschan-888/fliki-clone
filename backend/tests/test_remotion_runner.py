import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from workers import remotion_runner


class RemotionRunnerTest(unittest.TestCase):
    def test_remotion_output_line_yields_frame_progress(self):
        parse_progress = getattr(remotion_runner, "parse_render_progress", None)
        self.assertIsNotNone(parse_progress)
        self.assertEqual(parse_progress("Rendered 75/150, time remaining: 4s"), 44)
        self.assertEqual(parse_progress("Rendered 150/150"), 87)
        self.assertIsNone(parse_progress("Bundling 100%"))
    def test_frame_progress_reserves_finalization_range(self):
        progress_for_frame = getattr(remotion_runner, "render_progress_for_frame", None)
        self.assertIsNotNone(progress_for_frame)
        self.assertEqual(progress_for_frame(0, 150), 0)
        self.assertLess(progress_for_frame(75, 150), 87)
        self.assertEqual(progress_for_frame(150, 150), 87)
    def test_thumbnail_commands_create_full_and_preview_jpegs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            ffmpeg = Path(temp_dir) / "ffmpeg.exe"
            ffmpeg.touch()
            with patch.dict(os.environ, {"FFMPEG_EXECUTABLE": str(ffmpeg)}):
                build_commands = getattr(remotion_runner, "build_thumbnail_commands", None)
                self.assertIsNotNone(build_commands)
                commands = build_commands(
                    Path("video.mp4"),
                    Path("job_thumb.jpg"),
                    Path("job_thumbPreview.jpg"),
                )

        self.assertEqual(commands[0][0], str(ffmpeg))
        self.assertEqual(commands[0][-1], "job_thumb.jpg")
        self.assertIn("scale=320:-2", commands[1])
        self.assertEqual(commands[1][-1], "job_thumbPreview.jpg")
    def test_windows_uses_installed_browser_when_override_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            browser = Path(temp_dir) / "chrome.exe"
            browser.touch()
            with patch.dict(os.environ, {"REMOTION_BROWSER_EXECUTABLE": ""}, clear=False):
                with patch.object(
                    remotion_runner,
                    "WINDOWS_BROWSER_CANDIDATES",
                    (str(browser),),
                    create=True,
                ):
                    with patch.object(remotion_runner.platform, "system", return_value="Windows"):
                        with patch.object(
                            remotion_runner.shutil, "which", return_value="npx.cmd"
                        ):
                            command = remotion_runner.build_render_command(
                                Path("props.json"), Path("output.mp4")
                            )

        self.assertIn("--browser-executable", command)
        option_index = command.index("--browser-executable")
        self.assertEqual(command[option_index + 1], str(browser))
    def test_render_command_passes_configured_browser_executable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            browser = Path(temp_dir) / "chrome.exe"
            browser.touch()
            with patch.dict(os.environ, {"REMOTION_BROWSER_EXECUTABLE": str(browser)}):
                build_command = getattr(remotion_runner, "build_render_command", None)
                self.assertIsNotNone(build_command)
                command = build_command(Path("props.json"), Path("output.mp4"))

        option_index = command.index("--browser-executable")
        self.assertEqual(command[option_index + 1], str(browser))


    def test_render_command_passes_public_directory_from_props(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            public_dir = root / "public"
            public_dir.mkdir()
            props = root / "props.json"
            props.write_text(json.dumps({"_publicDir": str(public_dir)}), encoding="utf-8")
            command = remotion_runner.build_render_command(props, root / "output.mp4")

        option_index = command.index("--public-dir")
        self.assertEqual(command[option_index + 1], str(public_dir))

if __name__ == "__main__":
    unittest.main()
