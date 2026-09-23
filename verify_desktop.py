"""Developer smoke tests for a complete local video-to-shorts job.

Run with the project's virtual environment. Does not need a YouTube request.
"""
import argparse
import json
from pathlib import Path
import subprocess
import threading
import time

from pipeline import Settings, run
from runtime import DATA, NO_WINDOW, hardware, probe, tool


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="downloads/v9QtM6qnG50.mp4")
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()
    print(json.dumps(hardware()), flush=True)
    source = Path(args.source).resolve()
    sample = DATA / "outputs/desktop-test-source.mp4"
    sample.parent.mkdir(parents=True, exist_ok=True)
    if not args.full:
        subprocess.run([tool("ffmpeg"), "-y", "-v", "error", "-ss", "140", "-i", str(source), "-t", "75", "-c:v", "h264_nvenc", "-preset", "p4", "-c:a", "aac", str(sample)], check=True, creationflags=NO_WINDOW)
        source = sample
    last = [None]
    messages = []
    def progress(stage, value, message):
        messages.append(message)
        key = (stage, int((value or 0) * 10))
        if key != last[0] or value is None:
            print(stage, value, message, flush=True)
            last[0] = key
    start = time.monotonic()
    result = run(Settings(str(source), str(DATA / "outputs/desktop-verification"), count=3 if args.full else 2, duration=30), progress, threading.Event())
    for clip in result["clips"]:
        info = probe(clip["path"])
        assert (info["width"], info["height"]) == (1080, 1920), info
        assert abs(info["duration"] - (clip["end"] - clip["start"])) < .3, info
        assert clip["encoder"] == "h264_nvenc", clip
        assert Path(clip["path"]).with_suffix(".ass").exists()
    assert result['transcription_device'] in ('cuda', 'cache'), result['transcription_device']
    result["elapsed_seconds"] = round(time.monotonic() - start, 1)
    report = DATA / "outputs/desktop-verification.json"
    report.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"PASS: {len(result['clips'])} clips verified in {result['elapsed_seconds']}s. Report: {report}", flush=True)


if __name__ == "__main__":
    main()
