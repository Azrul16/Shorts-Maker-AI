"""Versioned local edit drafts and atomic job manifests; never store API keys."""
from dataclasses import asdict
from pathlib import Path
import json
import math
import os
import tempfile
from selector import Clip
from keyframes import validate_keyframes

VERSION = 1
SETTINGS_FIELDS = {'count','duration','model','height','follow','zoom','captions','gpu','framing',
                   'music','music_level','selection','use_groq','output','normalize_audio','caption_style'}


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    # Unique temp names also avoid collisions between simultaneous app instances.
    fd, temporary = tempfile.mkstemp(prefix=path.name+'.',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as handle:
            json.dump(data,handle,ensure_ascii=False,indent=2,allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary,path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def make_draft(source, title, media, clips, transcript, settings, *, downloaded=False, source_url=None):
    source = Path(source).resolve()
    stat = source.stat()
    return dict(version=VERSION,source=str(source),fingerprint={'size':stat.st_size,'mtime_ns':stat.st_mtime_ns},
                title=title,media=media,clips=[c.to_dict() for c in clips],transcript=transcript,
                settings={k:v for k,v in asdict(settings).items() if k in SETTINGS_FIELDS},
                downloaded=bool(downloaded),source_url=source_url)


def validate_draft(data, check_source=True):
    if not isinstance(data,dict) or data.get('version') != VERSION:
        raise ValueError('This project version is not supported.')
    source = Path(data['source']).expanduser().resolve()
    if check_source:
        if not source.is_file():
            raise ValueError('The original video for this draft is missing. Restore it before resuming.')
        stat = source.stat()
        if data.get('fingerprint') != {'size':stat.st_size,'mtime_ns':stat.st_mtime_ns}:
            raise ValueError('The source video changed since this draft was saved. Start a new project.')
    duration = float(data['media']['duration'])
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError('Invalid source duration in project.')
    if not data.get('clips') or len(data['clips']) > 100:
        raise ValueError('Select between 1 and 100 clips.')
    if 'checked' in data and (len(data['checked'])!=len(data['clips']) or not all(isinstance(v,bool) for v in data['checked'])):
        raise ValueError('Invalid saved clip selections.')
    for item in data['clips']:
        clip = Clip(**item)
        if not all(math.isfinite(v) for v in (clip.start,clip.end,clip.score)) or not 0 <= clip.start < clip.end <= duration+.05 or clip.end-clip.start > 180:
            raise ValueError('Clip times must be within the video and at most 180 seconds long.')
        if not isinstance(clip.title,str) or len(clip.title)>300:
            raise ValueError('A clip title must be 300 characters or fewer.')
        validate_keyframes(clip.crop_keyframes,clip.start,clip.end)
        if clip.caption_style not in ('classic','clean','bold'):
            raise ValueError('Unknown caption style in project.')
    if not isinstance(data.get('transcript'),list):
        raise ValueError('Invalid project transcript.')
    for segment in data['transcript']:
        if not isinstance(segment.get('text'),str) or not all(math.isfinite(float(segment[k])) for k in ('start','end')):
            raise ValueError('Invalid transcript segment.')
        if not 0 <= segment['start'] <= segment['end'] <= duration+.5:
            raise ValueError('Transcript timing is outside the source video.')
    if not isinstance(data.get('settings'),dict) or any(k not in SETTINGS_FIELDS for k in data['settings']):
        raise ValueError('Invalid or private settings in project.')
    return data


def load_draft(path):
    path = Path(path)
    if path.stat().st_size > 50*1024*1024:
        raise ValueError('Project file is too large.')
    return validate_draft(json.loads(path.read_text(encoding='utf-8')))
