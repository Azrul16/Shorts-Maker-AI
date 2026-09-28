"""One cancellable desktop job, with cached word timings and per-stage progress."""
from dataclasses import dataclass, field
from pathlib import Path
import hashlib
import json
import re

from downloader import DOWNLOAD_DIR, download_video
from renderer import render_clip
from runtime import DATA, check_cancel, hardware, probe
from selector import select_clips, complete_selection
from publishing import write_upload_details
from selector import Clip
from music import music_path, select_music, manual_music_info
from activity import select_activity
from transcriber import transcribe
from projects import atomic_json, make_draft, validate_draft
from quality import export_report


@dataclass
class Settings:
    source: str
    output: str = str(DATA / "shorts")
    count: int = 3
    duration: int = 60
    model: str = "small"
    height: int = 1920
    follow: bool = True
    zoom: bool = True
    captions: bool = True
    gpu: bool = True
    framing: str = "fill"
    music: str = "auto"
    music_level: float = .18
    manual_start: float | None = None
    manual_end: float | None = None
    selection: str = "auto"
    use_groq: bool = False
    groq_key: str = field(default='', repr=False)
    review: bool = False
    caption_style: str = 'classic'
    normalize_audio: bool = True


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


def run(settings, emit, cancel=None, *, review=None, prepared=None):
    # emit(stage index, fraction or None, message); no UI calls from this thread.
    emit(0, None, "Checking local processing hardware…")
    hw = hardware()
    if prepared is not None:
        validate_draft(prepared)
        settings.source = prepared['source']
    if settings.count < 1 or not 1 <= settings.duration <= 180:
        raise ValueError("Choose at least one short and a target length between 1 and 180 seconds.")
    music_path(settings.music)
    check_cancel(cancel)
    source = settings.source.strip()
    downloaded = source.startswith(("https://", "http://"))
    metadata = {}
    if prepared is not None:
        downloaded = prepared.get('downloaded',False)
        metadata = {'title':prepared['title'],'url':prepared.get('source_url')}
    elif downloaded:
        source = download_video(source, progress=lambda p, m: emit(0, p, m), cancel=cancel, metadata=metadata)
    else:
        if not Path(source).is_file():
            raise ValueError("Paste a video URL or choose an existing local video.")
        source = str(Path(source).resolve())
    title = metadata.get("title") or Path(source).stem
    selection = settings.selection
    if selection == "auto":
        if re.search(r"\b(football|soccer|la liga|premier league|bellingham|real madrid|goals?)\b", title, re.I):
            selection = "football"
        elif re.search(r"\b(animation|animated|cartoon|anime)\b", title, re.I):
            selection = "animation"
        elif re.search(r"\b(movie|film|cinema)\b", title, re.I):
            selection = "movie"
        elif re.search(r"\b(mrbeast|challenge|giveaway|survive)\b", title, re.I):
            selection = "challenge"
        else:
            selection = "action" if re.search(r"\b(highlights?|basketball|nba)\b", title, re.I) else "speech"
    check_cancel(cancel)
    media = probe(source)
    if settings.manual_start is not None or settings.manual_end is not None:
        if settings.manual_start is None or settings.manual_end is None or not 0 <= settings.manual_start < settings.manual_end <= media['duration']:
            raise ValueError("The chosen moment must have a start before its end, within the video duration.")
        if settings.manual_end-settings.manual_start > 180:
            raise ValueError("Choose an exact moment of 180 seconds or less for a YouTube Short.")
    emit(0, 1, f"Video ready · {media['duration'] / 60:.1f} min")
    cache_dir = DATA / "transcripts"
    cache_dir.mkdir(parents=True, exist_ok=True)
    stat = Path(source).stat()
    key = hashlib.sha256(f"{source}|{stat.st_size}|{stat.st_mtime_ns}|{settings.model}|words-v2".encode()).hexdigest()[:16]
    cache = cache_dir / f"{Path(source).stem}-{key}.json"
    transcript = prepared['transcript'] if prepared is not None else None
    transcription_device = "cache"
    if transcript is None and cache.exists():
        try:
            transcript = json.loads(cache.read_text(encoding="utf-8"))
            if not isinstance(transcript, list) or not all(isinstance(s, dict) and all(k in s for k in ('start', 'end', 'text', 'words')) for s in transcript):
                transcript = None
        except (ValueError, OSError):
            transcript = None
    if prepared is None and (not media.get("has_audio", True) or (selection in ("action", "football") and not settings.captions and not settings.use_groq)):
        transcript = []
        transcription_device = "skipped"
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
    if prepared is not None:
        clips = [Clip(**item) for item in prepared['clips']]
    elif settings.manual_start is not None:
        text = next((s['text'] for s in transcript if s['end'] > settings.manual_start), title)
        clips = [Clip(settings.manual_start, settings.manual_end, text[:68], 0, "Moment selected by you")]
    elif not media.get("has_audio", True):
        clips = []
    elif selection in ("action", "football") or not transcript:
        if not transcript and selection == 'speech':
            selection = 'action'
        clips = select_activity(source, media['duration'], settings.count, settings.duration, progress=lambda p, m: emit(2, p, m), cancel=cancel, football=selection == 'football', transcript=transcript)
    else:
        try:
            clips = select_clips(transcript, settings.count, settings.duration, media["duration"])
        except ValueError:
            clips = []
    if prepared is None and settings.manual_start is None and len(clips) < min(settings.count, max(1, int(media["duration"] / min(12, settings.duration)))) and media.get("has_audio", True):
        emit(2, None, "Finding additional distinct action scenes to fill the requested count...")
        extra = select_activity(source, media["duration"], settings.count, settings.duration, cancel=cancel, football=selection == "football", transcript=transcript)
        for candidate in sorted(extra, key=lambda c: c.score, reverse=True):
            if len(clips) >= settings.count:
                break
            if all(candidate.end <= other.start or candidate.start >= other.end for other in clips):
                clips.append(candidate)
    count_warning = None
    if prepared is not None:
        count_warning = 'Resumed saved clip choices; no new selection or transcription was needed.'
    elif settings.manual_start is None:
        clips = complete_selection(clips, media["duration"], settings.count, settings.duration)
        if len(clips) < settings.count:
            count_warning = f"Requested {settings.count}; source is too short for that many distinct clips (minimum 12 seconds, or target length if shorter). Exporting {len(clips)}."
    else:
        count_warning = "Exact moment mode exports one short. Turn it off to use the Shorts count."
    selection_label = "manual timestamps" if settings.manual_start is not None else {'action': 'audio activity', 'football': 'audio activity with football scene checks', 'speech': 'standalone speech scoring', 'movie': 'movie dialogue with scene fallback', 'animation': 'animation dialogue with scene fallback', 'challenge': 'challenge dialogue with scene fallback'}[selection]
    emit(2, 1, f"Selected {len(clips)} clips using {selection_label}")
    if prepared is None:
        for clip in clips:
            clip.caption_style = settings.caption_style
    if settings.review and review is not None:
        # User review runs on the GUI thread; this worker waits cancellably.
        effective = Settings(**{**settings.__dict__, 'selection':selection})
        draft = make_draft(source,title,media,clips,transcript,effective,downloaded=downloaded,source_url=metadata.get('url'))
        if prepared is not None and 'checked' in prepared:
            draft['checked'] = prepared['checked'][:]
        emit(2,None,'Review your clips, captions and crop before exporting.')
        reviewed = review(draft)
        check_cancel(cancel)
        if reviewed is None:
            from runtime import Cancelled
            raise Cancelled('Draft saved. Export was not started.')
        validate_draft(reviewed)
        clips = [Clip(**item) for item in reviewed['clips']]
        transcript = reviewed['transcript']
        count_warning = f'Exporting {len(clips)} clips selected in review.'
        emit(2,1,'Review complete. Exporting your edited clips.')
    output = create_output_folder(settings.output, title)
    manifest = {"source": source, "title": title, "source_url": metadata.get("url"), "source_deleted": False, "hardware": hw, "transcription_device": transcription_device, "selection": selection_label, "transcript": str(cache) if cache.exists() else None, "requested_count": settings.count, "selected_count": len(clips), "count_warning": count_warning, "clips": []}
    atomic_json(output/'transcript.json',transcript)
    manifest['transcript'] = str(output/'transcript.json')
    manifest_path = output / "project.json"
    atomic_json(manifest_path,manifest)
    for i, clip in enumerate(clips):
        check_cancel(cancel)
        def progress(p, message):
            emit(3, (i + (p or 0)) / len(clips), f"Short {i+1}/{len(clips)} · {message}")
        options = dict(height=settings.height, follow=settings.follow, zoom=settings.zoom, captions=settings.captions, nvenc=hw["nvenc"] and settings.gpu, progress=progress, cancel=cancel, framing="fill" if selection == "football" else settings.framing, tracking="ball" if selection == "football" else "face", music=settings.music, music_level=settings.music_level)
        options['normalize_audio'] = settings.normalize_audio
        path = output / f"{i+1:02} - {safe_name(clip.title, 65)}.mp4"
        music_info = manual_music_info(settings.music)
        if settings.music == 'auto':
            progress(None, 'Matching background music to this scene...')
            music_info = select_music(source, clip, transcript, selection, cancel)
            options.update(music=music_info['path'], music_offset=music_info['offset'])
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
        quality = export_report(path,exported,result,clip.end-clip.start,settings.height)
        if not quality['technical_pass']:
            raise RuntimeError('Export quality checks failed. The original video has been kept.')
        check_cancel(cancel)
        progress(None, 'Writing YouTube title, description and hashtags...')
        upload = write_upload_details(path, title, clip, transcript, selection, i+1, metadata.get("url"), use_groq=settings.use_groq, api_key=settings.groq_key, music_credit=music_info['credit'] if music_info else '')
        if upload.get('warning'):
            emit(3, i/len(clips), upload['warning'])
        manifest["clips"].append({**clip.to_dict(), **result, "youtube": upload, "music_selection": music_info, 'quality':quality})
        atomic_json(manifest_path,manifest)
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
        atomic_json(manifest_path,manifest)
    if count_warning:
        emit(3, 1, count_warning)
    emit(3, 1, f"Finished · {len(clips)} vertical shorts saved")
    return {"folder": str(output), **manifest}
