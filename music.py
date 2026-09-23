"""Background music selection and speech-ducked FFmpeg audio mixing."""
from pathlib import Path
import math
from runtime import ASSETS

TRACKS = {"ambient": "soft_ambient.wav", "beat": "light_beat.wav"}


def music_path(selection):
    if not selection or selection == "off":
        return None
    path = ASSETS / "assets/music" / TRACKS[selection] if selection in TRACKS else Path(selection).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"Background music file not found: {path}")
    return path


def audio_filter(duration, level=.18):
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
        "alimiter=limit=0.95:level=0:latency=1[mixed]"
    )
