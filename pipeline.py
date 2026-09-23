"""One cancellable desktop job, with cached word timings and per-stage progress."""
from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import re

from downloader import DOWNLOAD_DIR, download_video
from renderer import render_clip
from runtime import DATA, check_cancel, hardware, probe
from selector import select_clips
from transcriber import transcribe


@dataclass
class Settings:
    source: str
    output: str = str(DATA / "shorts")
    count: int = 3
    duration: int = 40
    model: str = "small"
    height: int = 1920
    follow: bool = True
    zoom: bool = True
    captions: bool = True
    gpu: bool = True


def safe_name(title, limit=90):
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", title)
    name = re.sub(r"\s+", " ", name).strip(" .")[:limit].rstrip(" .") or "Untitled video"
    if re.match(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", name, re.I):
        name = "_" + name
    return name


def create_output_folder(base, title):
    root = Path(base).expanduser().resolve()
    if root.name.lower() != "shorts":
        root /= "shorts"
    root.mkdir(parents=True, exist_ok=True)
    name = safe_name(title)
    number = 1
    while True:
        folder = root / (name if number == 1 else f"{name} ({number})")
        try:
            folder.mkdir()
            return folder
        except FileExistsError:
            number += 1


def run(settings, emit, cancel=None):
    # emit(stage index, fraction or None, message); no UI calls from this thread.
    emit(0, None, "Checking local processing hardware…")
    hw = hardware()
    check_cancel(cancel)
    source = settings.source.strip()
    downloaded = source.startswith(("https://", "http://"))
    metadata = {}
    if downloaded:
        source = download_video(source, progress=lambda p, m: emit(0, p, m), cancel=cancel, metadata=metadata)
    else:
        if not Path(source).is_file():
            raise ValueError("Paste a video URL or choose an existing local video.")
        source = str(Path(source).resolve())
    title = metadata.get("title") or Path(source).stem
    check_cancel(cancel)
    media = probe(source)
    emit(0, 1, f"Video ready · {media['duration'] / 60:.1f} min")
    cache_dir = DATA / "transcripts"
    cache_dir.mkdir(parents=True, exist_ok=True)
    stat = Path(source).stat()
    key = hashlib.sha256(f"{source}|{stat.st_size}|{stat.st_mtime_ns}|{settings.model}|words-v2".encode()).hexdigest()[:16]
    cache = cache_dir / f"{Path(source).stem}-{key}.json"
    transcript = None
    transcription_device = "cache"
    if cache.exists():
        try:
            transcript = json.loads(cache.read_text(encoding="utf-8"))
            if not isinstance(transcript, list) or not all(isinstance(s, dict) and all(k in s for k in ('start', 'end', 'text', 'words')) for s in transcript):
                transcript = None
        except (ValueError, OSError):
            transcript = None
    if transcript is None:
        def transcript_progress(value, message):
            nonlocal transcription_device
            if message.startswith("Transcribed"):
                transcription_device = "cuda" if "CUDA" in message else "cpu"
            emit(1, value, message)
        transcript = transcribe(source, settings.model, device="auto" if settings.gpu else "cpu", progress=transcript_progress, cancel=cancel, word_timestamps=True)
        cache.write_text(json.dumps(transcript, ensure_ascii=False, indent=2), encoding="utf-8")
    emit(1, 1, f"Transcript ready · {len(transcript)} segments")
    check_cancel(cancel)
    emit(2, None, "Scoring complete speech windows and removing overlaps…")
    clips = select_clips(transcript, settings.count, settings.duration, media["duration"])
    emit(2, 1, f"Selected {len(clips)} clips using local transcript scoring")
    output = create_output_folder(settings.output, title)
    manifest = {"source": source, "title": title, "source_url": metadata.get("url"), "source_deleted": False, "hardware": hw, "transcription_device": transcription_device, "selection": "Local heuristic scoring; review clips before sharing", "transcript": str(cache), "clips": []}
    manifest_path = output / "project.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    for i, clip in enumerate(clips):
        check_cancel(cancel)
        def progress(p, message):
            emit(3, (i + (p or 0)) / len(clips), f"Short {i+1}/{len(clips)} · {message}")
        options = dict(height=settings.height, follow=settings.follow, zoom=settings.zoom, captions=settings.captions, nvenc=hw["nvenc"] and settings.gpu, progress=progress, cancel=cancel)
        path = output / f"{i+1:02} - {safe_name(clip.title, 65)}.mp4"
        try:
            result = render_clip(source, clip, transcript, path, **options)
        except RuntimeError as exc:
            check_cancel(cancel)
            if not options["nvenc"]:
                raise
            emit(3, i / len(clips), f"GPU render failed; retrying on CPU: {exc}")
            options["nvenc"] = False
            result = render_clip(source, clip, transcript, path, **options)
        exported = probe(result["path"])
        if abs(exported["duration"] - (clip.end - clip.start)) > .5 or exported["height"] != settings.height:
            raise RuntimeError("Export verification failed. The original video has been kept.")
        manifest["clips"].append({**clip.to_dict(), **result})
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    check_cancel(cancel)
    if downloaded and manifest["clips"]:
        original = Path(source).resolve()
        if original.parent != DOWNLOAD_DIR.resolve():
            manifest["cleanup_warning"] = "Downloaded file was outside the app downloads folder; it was kept."
        else:
            try:
                original.unlink()
                manifest["source_deleted"] = True
            except OSError as exc:
                manifest["cleanup_warning"] = f"Shorts saved, but the downloaded original could not be deleted: {exc}"
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    emit(3, 1, f"Finished · {len(clips)} vertical shorts saved")
    return {"folder": str(output), **manifest}
