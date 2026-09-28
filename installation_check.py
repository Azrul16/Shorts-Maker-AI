"""Explicit developer check of the frozen app's bundled engine, without internet."""
from pathlib import Path
import json
import subprocess
import traceback
import os

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
        start = min(40, max(0, probe(source)['duration']-6))
        subprocess.run([tool("ffmpeg"), "-y", "-v", "error", "-ss", str(start), "-i", str(source), "-t", "6", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", str(sample)], check=True, creationflags=NO_WINDOW)
        messages = []
        transcript = transcribe(str(sample), word_timestamps=True, progress=lambda p, m: messages.append(m))
        result["transcription_messages"] = messages
        result["segments"] = len(transcript)
        clip = Clip(0, 5, "Installation check", 0, "")
        options = {}
        if os.environ.get('SHORTMAKER_VERIFY_EDITING') == '1':
            from keyframes import KeyframeCamera
            from review import ReviewDialog
            clip.crop_keyframes = [dict(time=0,x=.35,y=.5,zoom=1.05),dict(time=5,x=.65,y=.5,zoom=1.15)]
            clip.caption_style = 'bold'
            options['normalize_audio'] = True
        if os.environ.get('SHORTMAKER_VERIFY_FOOTBALL') == '1':
            options.update(tracking='ball', framing='fill')
        rendered = render_clip(sample, clip, transcript, report.parent / "install-check-short.mp4", nvenc=result["hardware"]["nvenc"], **options)
        if os.environ.get('SHORTMAKER_VERIFY_COPY') == '1':
            from publishing import write_upload_details
            result['youtube'] = write_upload_details(report.parent/'install-check-short.mp4',
                'Installation check', clip, transcript, 'speech', 1, use_groq=True)
        result["render"] = rendered
        result["media"] = probe(rendered["path"])
        from quality import export_report
        result['quality'] = export_report(rendered['path'],result['media'],rendered,5,1920)
        result["ok"] = bool(transcript) and result["media"]["height"] == 1920
        result['ok'] = result['ok'] and result['quality']['technical_pass']
    except Exception:
        result["error"] = traceback.format_exc()
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if result["ok"] else 1
