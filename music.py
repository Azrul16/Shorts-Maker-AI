"""Background music selection and speech-ducked FFmpeg audio mixing."""
from pathlib import Path
import math
import json
import random
import threading
import subprocess
import numpy as np
from functools import lru_cache
from runtime import ASSETS, DATA
from story import story_plan

_HISTORY_LOCK = threading.Lock()


@lru_cache(maxsize=1)
def catalog():
    return [t for t in json.loads((ASSETS/'assets/music/catalog.json').read_text(encoding='utf-8'))
            if (ASSETS/'assets/music'/t['file']).is_file()]


def track_credit(track):
    if track.get('license') != 'CC BY 4.0':
        return ''
    return (f"{track['title']} - {track['artist']} (incompetech.com)\n"
            "Licensed under Creative Commons Attribution 4.0: https://creativecommons.org/licenses/by/4.0/\n"
            f"Source: {track['source']}\nMusic excerpt mixed under original audio.")


def manual_music_info(selection):
    path = music_path(selection)
    if path is None:
        return None
    for track in catalog():
        if (ASSETS/'assets/music'/track['file']).resolve() == path.resolve():
            return {**track, 'path': str(path), 'offset': 0., 'credit': track_credit(track), 'reason': 'Selected by you'}
    return None


def choose_track(tracks, mood, history_path=None):
    """Use every matching composition before repeating, including across app runs."""
    candidates = [t for t in tracks if t['mood'] == mood] or tracks
    if not candidates:
        raise ValueError('No background music files are available. Choose your own music or turn music off.')
    path = Path(history_path) if history_path else DATA/'music-history.json'
    with _HISTORY_LOCK:
        try:
            history = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(history, dict): history = {}
        except (OSError, ValueError):
            history = {}
        used = history.get(mood, [])
        if not isinstance(used, list): used = []
        used_files = set(used)
        available = [t for t in candidates if t['file'] not in used_files]
        if not available:
            available = [t for t in candidates if not used or t['file'] != used[-1]] or candidates
            used = []
        track = random.SystemRandom().choice(available)
        history[mood] = used + [track['file']]
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix('.tmp')
            temporary.write_text(json.dumps(history), encoding='utf-8')
            temporary.replace(path)
        except OSError:
            pass
    return track


def music_path(selection):
    if selection == 'auto':
        return None  # resolved per clip, after its content has been selected
    if not selection or selection == "off":
        return None
    path = Path(selection).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"Background music file not found: {path}")
    return path


@lru_cache(maxsize=24)
def first_beat(path):
    from runtime import tool, NO_WINDOW
    result = subprocess.run([tool('ffmpeg'), '-v', 'error', '-i', str(path), '-t', '8', '-ac', '1', '-ar', '8000', '-f', 'f32le', 'pipe:1'], capture_output=True, creationflags=NO_WINDOW, timeout=20)
    if result.returncode or len(result.stdout) < 320:
        return 0.
    samples = np.frombuffer(result.stdout, dtype='<f4')
    energy = np.mean(samples[:len(samples)//160*160].reshape(-1, 160)**2, axis=1)
    onset = np.maximum(0, np.diff(energy, prepend=0))
    peaks = np.flatnonzero(onset > max(float(onset.max())*.55, 1e-7))
    return max(0., float(peaks[0])*.02-.02) if len(peaks) else 0.


def select_music(source, clip, transcript, category, cancel=None):
    from runtime import check_cancel
    check_cancel(cancel)
    mood = story_plan(transcript,clip)['mood']
    tags = {'suspense':('dark','suspense','intense','eerie'),
            'celebration':('uplifting','bright','bouncy','grooving'),
            'playful':('humorous','bouncy','grooving'),
            'drive':('driving','action','aggressive')}[mood]
    tracks = catalog()
    matching = [t for t in tracks if any(tag in t.get('tags','').lower() for tag in tags)]
    track = choose_track(matching if len(matching)>=5 else tracks,'energetic')
    path = ASSETS/'assets/music'/track['file']
    return {**track,'path':str(path),'offset':track['onset'] if 'onset' in track else first_beat(str(path)),
            'credit':track_credit(track),'vibe':mood,'reason':f'{mood.title()} dialogue cues matched to artist track tags; rotation avoids repeats'}


def audio_filter(duration, level=.18, normalize=False):
    """Source is input 1, looping music input 2; speech remains at original gain."""
    if not math.isfinite(level) or not 0 <= level <= 1:
        raise ValueError("Music level must be between 0 and 1.")
    fade = min(1.5, duration / 3)
    return (
        "[1:a:0]aresample=48000,asetpts=PTS-STARTPTS,asplit=2[voice][side];"
        f"[2:a:0]aresample=48000,asetpts=PTS-STARTPTS,volume={level:.4f},"
        f"afade=t=in:d={min(.6, fade):.3f},afade=t=out:st={max(0, duration-fade):.3f}:d={fade:.3f}[bed];"
        "[bed][side]sidechaincompress=threshold=0.025:ratio=8:attack=15:release=350:makeup=1[ducked];"
        "[voice][ducked]amix=inputs=2:duration=first:normalize=0,"
        + ("loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000," if normalize else "")
        + "alimiter=limit=0.95:level=0:latency=1[mixed]"
    )
