"""Streaming audio fallback for challenge clips without usable dialogue."""
import subprocess
import tempfile
import numpy as np
from runtime import NO_WINDOW, check_cancel, tool
from selector import Clip


def choose_activity_windows(energy, duration, count=3, target=40, step=.25):
    if len(energy) == 0:
        raise ValueError("Could not analyze the video's audio.")
    values = np.asarray(energy, dtype=float)
    def smooth(seconds):
        n = min(len(values), max(1, round(seconds/step)))
        # Zero padding would make the start/end look artificially exciting.
        padded = np.pad(values, (n//2, n-1-n//2), mode='edge')
        return np.convolve(padded, np.ones(n)/n, mode='valid')
    burst, context = smooth(2), smooth(30)
    scores = .35*burst/(context+.002) + .65*burst/max(.001, float(np.max(burst)))
    # Ignore isolated clicks and allow enough room for the build-up and reaction.
    selected = []
    length = min(duration, target)
    for index in np.argsort(scores)[::-1]:
        peak = min(duration, (int(index)+.5)*step)
        if duration > target*2 and not target*.55 <= peak <= duration-target*.45:
            continue
        start = max(0, min(duration-length, peak-length*.55))
        end = min(duration, start+length)
        if any(start < other.end and end > other.start for other in selected):
            continue
        minute, second = divmod(int(peak), 60)
        selected.append(Clip(start, end, f"Action highlight at {minute:02}:{second:02}", round(float(scores[index])*50, 1), "Audio activity peak with lead-in and reaction; review the visual event"))
        if len(selected) >= count:
            break
    return sorted(selected, key=lambda clip: clip.start)


def select_activity(source, duration, count=3, target=40, progress=None, cancel=None):
    command = [tool('ffmpeg'), '-v', 'error', '-nostdin', '-i', str(source), '-vn', '-ac', '1', '-ar', '8000', '-f', 'f32le', 'pipe:1']
    energy = []
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errors, creationflags=NO_WINDOW)
        try:
            while True:
                check_cancel(cancel)
                chunk = process.stdout.read(8000)
                if not chunk:
                    break
                samples = np.frombuffer(chunk[:len(chunk)//4*4], dtype='<f4')
                if len(samples):
                    energy.append(float(np.sqrt(np.mean(samples*samples))))
                if progress and len(energy) % 20 == 0:
                    progress(min(.99, len(energy)*.25/max(duration, 1)), "Finding activity peaks and their lead-up…")
            if process.wait(timeout=30):
                errors.seek(0)
                raise RuntimeError(errors.read().decode('utf-8', errors='replace')[-1000:])
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            process.stdout.close()
    return choose_activity_windows(energy, duration, count, target)
