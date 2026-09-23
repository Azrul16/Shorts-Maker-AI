"""Explicit developer check of the frozen app's bundled engine, without internet."""
from pathlib import Path
import json
import subprocess
import traceback

from runtime import ASSETS, DATA, NO_WINDOW, hardware, probe, tool
from transcriber import transcribe
from renderer import render_clip
from selector import Clip


def verify(source, report):
    report = Path(report).resolve()
    report.parent.mkdir(parents=True, exist_ok=True)
    result = {"ok": False, "assets": str(ASSETS)}
    try:
        result["hardware"] = hardware()
        result["bundled_model"] = (ASSETS / "models/small/model.bin").is_file()
        result["bundled_node"] = (ASSETS / "tools/node.exe").is_file()
        source = Path(source).resolve()
        sample = report.parent / "install-check-source.mp4"
        subprocess.run([tool("ffmpeg"), "-y", "-v", "error", "-ss", "40", "-i", str(source), "-t", "6", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", str(sample)], check=True, creationflags=NO_WINDOW)
        messages = []
        transcript = transcribe(str(sample), word_timestamps=True, progress=lambda p, m: messages.append(m))
        result["transcription_messages"] = messages
        result["segments"] = len(transcript)
        clip = Clip(0, 5, "Installation check", 0, "")
        rendered = render_clip(sample, clip, transcript, report.parent / "install-check-short.mp4", nvenc=result["hardware"]["nvenc"])
        result["render"] = rendered
        result["media"] = probe(rendered["path"])
        result["ok"] = bool(transcript) and result["media"]["height"] == 1920
    except Exception:
        result["error"] = traceback.format_exc()
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if result["ok"] else 1
