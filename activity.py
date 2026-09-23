"""Audio-activity selection for sports/action, including clips with no speech."""
import subprocess
import tempfile
import cv2
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


def select_activity(source, duration, count=3, target=40, progress=None, cancel=None, football=False):
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
    candidates = choose_activity_windows(energy, duration, max(6, count*3) if football else count, target)
    if not football:
        return candidates
    # Audio alone can select an anthem or walk-on. Check for wide pitch views
    # during the lead-up. This is a visual heuristic, not goal recognition.
    capture = cv2.VideoCapture(str(source))
    try:
        for i, clip in enumerate(candidates):
            check_cancel(cancel)
            coverage = []
            for offset in (.2, .45):
                capture.set(cv2.CAP_PROP_POS_MSEC, (clip.start+(clip.end-clip.start)*offset)*1000)
                ok, frame = capture.read()
                if ok:
                    hsv = cv2.cvtColor(cv2.resize(frame, (160, 90)), cv2.COLOR_BGR2HSV)
                    pitch = cv2.inRange(hsv, (30, 40, 30), (90, 255, 255))
                    coverage.append(float(np.mean(pitch > 0)))
            visible = max(coverage, default=0)
            clip.score += 8*visible - (30 if visible < .5 else 0)
            clip.score = round(clip.score, 1)
            clip.reason += '; checked for a wide football pitch in the lead-up'
            if progress:
                progress((i+1)/len(candidates), f"Checking football scenes {i+1}/{len(candidates)}")
    finally:
        capture.release()
    return sorted(sorted(candidates, key=lambda c: c.score, reverse=True)[:count], key=lambda c: c.start)
