"""Explicit developer check of the frozen app's bundled engine, without internet."""
from pathlib import Path
import json
import subprocess
import traceback
import os

from runtime import ASSETS, NO_WINDOW, hardware, probe, tool
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
        if os.environ.get('SHORTMAKER_VERIFY_SUMMARY') == '1':
            clip.spans = [dict(start=.2,end=1.8),dict(start=3.,end=4.8)]
            clip.start, clip.end = .2, 4.8
            clip.caption_style = 'bold'
            clip.effects = 'energetic'
            options.update(music='auto',normalize_audio=True)

        if os.environ.get('SHORTMAKER_VERIFY_EDITING') == '1':
            clip.crop_keyframes = [dict(time=0,x=.35,y=.5,zoom=1.05),dict(time=5,x=.65,y=.5,zoom=1.15)]
            clip.caption_style = 'bold'
            clip.effects = 'energetic'
            options['normalize_audio'] = True
        rendered = render_clip(sample, clip, transcript, report.parent / "install-check-short.mp4", nvenc=result["hardware"]["nvenc"], **options)
        if os.environ.get('SHORTMAKER_VERIFY_COPY') == '1':
            from publishing import write_upload_details
            from summary import timeline
            edited_clip, edited_transcript = timeline(clip, transcript)
            result['youtube'] = write_upload_details(report.parent/'install-check-short.mp4',
                'Installation check', edited_clip, edited_transcript, 'challenge', 1, use_groq=True)
        result["render"] = rendered
        result["media"] = probe(rendered["path"])
        from quality import export_report
        result['quality'] = export_report(rendered['path'],result['media'],rendered,clip.duration,1920)
        result["ok"] = bool(transcript) and result["media"]["height"] == 1920
        result['ok'] = result['ok'] and result['quality']['technical_pass']
    except Exception:
        result["error"] = traceback.format_exc()
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if result["ok"] else 1


def verify_preview(app,source,report):
    """Exercise the packaged review event loop while the real decoder is busy."""
    import time
    from PySide6.QtCore import QTimer
    from review import ReviewDialog
    from projects import make_draft
    from pipeline import Settings
    source = Path(source).resolve()
    media = probe(source)
    end = min(9,media['duration'])
    draft = make_draft(source,'Preview check',media,[Clip(0,end,'Preview',1,'')],[],Settings(str(source),selection='challenge'))
    dialog = ReviewDialog(draft)
    beats,frames = [],[]
    dialog.worker.ready.connect(lambda frame:frames.append(frame['position']))
    timer = QTimer();timer.setInterval(10)
    timer.timeout.connect(lambda:beats.append(time.perf_counter()))
    def play():
        timer.start()
        dialog.toggle_play()
    def finish():
        dialog.pause()
        for i in range(50):
            dialog.seek((i*.137)%max(.1,end-.2))
        QTimer.singleShot(500,dialog.reject)
    dialog.show()
    QTimer.singleShot(300,play)
    QTimer.singleShot(4000,finish)
    app.exec()
    timer.stop()
    gaps=[1000*(b-a) for a,b in zip(beats,beats[1:])]
    result=dict(frames=len(frames),heartbeats=len(beats),max_ui_gap_ms=max(gaps,default=0),worker_stopped=not dialog.worker.isRunning())
    result['ok']=result['frames']>=10 and result['heartbeats']>=50 and result['max_ui_gap_ms']<1000 and result['worker_stopped']
    path=Path(report);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,indent=2),encoding='utf-8')
    return 0 if result['ok'] else 1
