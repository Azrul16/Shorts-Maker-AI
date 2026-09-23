"""Local, source-grounded YouTube copy; never invent events or promise reach."""
import re
from pathlib import Path


def write_upload_details(video, source_title, clip, transcript, category, number, source_url=None):
    clean = lambda text: re.sub(r'\s+', ' ', text).strip()
    source_title = clean(source_title)
    speech = clean(' '.join(s['text'] for s in transcript
                           if s['start'] >= clip.start and s['end'] <= clip.end))
    kind, tags = {
        'football': ('Football highlight', ['Shorts', 'Football', 'FootballHighlights']),
        'action': ('Sports / action highlight', ['Shorts', 'Highlights']),
        'movie': ('Movie scene', ['Shorts', 'MovieScene', 'Movies']),
        'animation': ('Animation scene', ['Shorts', 'Animation', 'AnimatedScene']),
    }.get(category, ('Video highlight', ['Shorts']))
    # A short actual line is more specific than a generic clickbait promise.
    hook = clean(clip.title)
    if clip.score == 0 or re.match(r'^(Action highlight at|Scene(?: at| \d))', hook):
        hook = kind
    suffix = f' | Clip {number}'
    prefix = f'{source_title[:45]}: {hook}'
    title = prefix[:100-len(suffix)].rstrip(' .') + suffix
    excerpt = speech[:280].rsplit(' ', 1)[0] + '…' if len(speech) > 280 else speech
    lines = [f'{kind} from {source_title}.']
    if excerpt:
        lines += ['', f'In this clip: “{excerpt}”']
    lines += ['', 'Which moment stood out to you?']
    if source_url:
        lines += ['', f'Source: {source_url}']
    hashtags = ' '.join('#'+tag for tag in tags)
    description = '\n'.join(lines) + '\n\n' + hashtags
    path = Path(video).with_suffix('.youtube.txt')
    path.write_text(f'TITLE\n{title}\n\nDESCRIPTION\n{description}\n\n'
                    'REVIEW BEFORE UPLOAD\n'
                    'Check the title, transcript, names and scene context. These are offline suggestions, not a guarantee of views.\n', encoding='utf-8')
    return {'title': title, 'description': description, 'hashtags': ['#'+tag for tag in tags], 'file': str(path)}
