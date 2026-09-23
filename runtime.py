"""Paths and process helpers shared by source and packaged applications."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import threading

FROZEN = getattr(sys, "frozen", False)
ASSETS = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
DATA = Path(os.environ.get("SHORTMAKER_DATA", str(Path.home() / "Documents" / "AI Short Maker" if FROZEN else ASSETS)))
NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
_dll_handles = []


class Cancelled(Exception):
    pass


def check_cancel(cancel: threading.Event | None):
    if cancel and cancel.is_set():
        raise Cancelled("Stopped by you. Completed clips have been kept.")


def tool(name):
    for folder in (ASSETS / ".tools/ffmpeg/bin", ASSETS / "tools", ASSETS / ".tools"):
        path = folder / (name + ".exe")
        if path.is_file():
            return str(path)
    found = shutil.which(name)
    if not found:
        raise RuntimeError(f"{name} is missing. Rebuild the app with the bundled tools.")
    return found


def enable_cuda_libraries():
    if os.name != "nt" or _dll_handles:
        return
    roots = [ASSETS / "nvidia", Path(sys.prefix) / "Lib/site-packages/nvidia"]
    for root in roots:
        if root.exists():
            for folder in root.glob("*/bin"):
                _dll_handles.append(os.add_dll_directory(str(folder)))
                os.environ["PATH"] = str(folder) + os.pathsep + os.environ.get("PATH", "")


def probe(path):
    import json
    result = subprocess.run([tool("ffprobe"), "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)], capture_output=True, text=True, creationflags=NO_WINDOW, timeout=30)
    if result.returncode:
        raise RuntimeError(f"Cannot read video: {result.stderr[-500:]}")
    info = json.loads(result.stdout)
    video = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    if not video:
        raise ValueError("Please choose a video file with a video track.")
    if not any(s["codec_type"] == "audio" for s in info["streams"]):
        raise ValueError("This video has no audio track to transcribe.")
    return {"duration": float(info["format"]["duration"]), "width": video["width"], "height": video["height"]}


def hardware():
    enable_cuda_libraries()
    import ctranslate2
    try:
        cuda = ctranslate2.get_cuda_device_count() > 0
    except Exception:
        cuda = False
    try:
        result = subprocess.run([tool("ffmpeg"), "-v", "error", "-f", "lavfi", "-i", "color=s=256x256:d=0.1", "-c:v", "h264_nvenc", "-f", "null", "-"], capture_output=True, creationflags=NO_WINDOW, timeout=20)
        nvenc = result.returncode == 0
    except (OSError, RuntimeError, subprocess.TimeoutExpired):
        nvenc = False
    try:
        result = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"], capture_output=True, text=True, creationflags=NO_WINDOW, timeout=5)
        name = result.stdout.strip().splitlines()[0] if result.returncode == 0 else "CPU"
    except (OSError, IndexError, subprocess.TimeoutExpired):
        name = "NVIDIA GPU" if cuda else "CPU"
    return {"name": name, "cuda": cuda, "nvenc": nvenc}
