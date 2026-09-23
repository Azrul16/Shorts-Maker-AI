"""Download one video and return its actual postprocessed filename."""

from pathlib import Path
import shutil
from urllib.parse import urlparse
from runtime import ASSETS, DATA, check_cancel

DOWNLOAD_DIR = DATA / "downloads"
LOCAL_FFMPEG = ASSETS / ".tools" / "ffmpeg" / "bin"


def download_video(url: str, *, progress=None, cancel=None, metadata=None) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Enter a valid http:// or https:// video URL.")
    local_ffmpeg = all((LOCAL_FFMPEG / name).is_file() for name in ("ffmpeg.exe", "ffprobe.exe"))
    if not local_ffmpeg and (not shutil.which("ffmpeg") or not shutil.which("ffprobe")):
        raise RuntimeError("FFmpeg and ffprobe must be on PATH. Install FFmpeg and reopen PowerShell.")

    import yt_dlp

    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    completed_paths = []

    def download_progress(status):
        check_cancel(cancel)
        if not progress:
            return
        total = status.get("total_bytes") or status.get("total_bytes_estimate")
        fraction = min(1, status.get("downloaded_bytes", 0) / total) if total else None
        if status["status"] == "downloading":
            progress(fraction, "Downloading video / audio")
        elif status["status"] == "finished":
            progress(None, "Merging video and audio…")

    class Logger:
        def debug(self, message):
            pass
        def warning(self, message):
            if progress:
                progress(None, message)
        def error(self, message):
            if progress:
                progress(None, message)

    def remember_path(filename):
        completed_paths.append(Path(filename))

    options = {
        "format": "bv*[height<=1080]+ba/b[height<=1080]",
        "merge_output_format": "mp4",
        "outtmpl": str(DOWNLOAD_DIR / "%(id)s.%(ext)s"),
        "noplaylist": True,
        "post_hooks": [remember_path],
        "js_runtimes": {"deno": {}, "node": {}},
        "progress_hooks": [download_progress],
    }
    node = ASSETS / "tools/node.exe"
    if node.is_file():
        options["js_runtimes"]["node"] = {"path": str(node)}
    if progress:
        options.update({"logger": Logger(), "quiet": True, "noprogress": True})
    if local_ffmpeg:
        options["ffmpeg_location"] = str(LOCAL_FFMPEG)
    with yt_dlp.YoutubeDL(options) as ydl:
        check_cancel(cancel)
        info = ydl.extract_info(url, download=True)
        if not info or info.get("_type") in {"playlist", "multi_video"}:
            raise RuntimeError("Please supply a single video URL, not a playlist.")
        if metadata is not None:
            metadata.update(title=info.get("title") or info["id"], video_id=info["id"], url=url)
        candidates = completed_paths + [Path(info.get("filepath") or ydl.prepare_filename(info))]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate.resolve())
    raise RuntimeError("The downloader did not produce a video file.")
