"""Fast checks for filename handling and CLI failures; no model download."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import downloader

ROOT = Path(__file__).resolve().parents[1]


class PipelineTests(unittest.TestCase):
    def test_download_returns_postprocessed_file(self):
        with tempfile.TemporaryDirectory() as directory:
            final = Path(directory) / "video.webm"

            class FakeDownloader:
                def __init__(self, options):
                    self.options = options

                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    pass

                def extract_info(self, url, download):
                    final.write_bytes(b"test media")
                    for callback in self.options["post_hooks"]:
                        callback(str(final))
                    return {"id": "video"}

                def prepare_filename(self, info):
                    return str(Path(directory) / "old.mp4")

            with patch("yt_dlp.YoutubeDL", FakeDownloader), patch("downloader.shutil.which", return_value="tool"), patch.object(downloader, "DOWNLOAD_DIR", Path(directory)):
                self.assertEqual(downloader.download_video("https://example.com/video"), str(final.resolve()))

    def test_invalid_url_is_rejected(self):
        with self.assertRaises(ValueError):
            downloader.download_video("not a URL")

    def test_missing_local_file_fails_without_loading_model(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "main.py"), "--file", str(ROOT / "does-not-exist.mp4")],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("Video not found", result.stderr)
        self.assertNotIn("Loading Whisper", result.stdout)


if __name__ == "__main__":
    unittest.main()
