"""Source-grounded challenge beats shared by selection, effects and music."""
from bisect import bisect_right
import re

PATTERNS = {
    'setup': re.compile(r"\b(?:last (?:one |person )?to|challenge|if you|whoever|has to|must|survive|prize|i (?:built|bought|spent|gave)|we (?:built|bought|spent)|donat\w*|cheapest|expensive|versus|dollars?|win[s]?|minutes? left|seconds? left)\b|\$\s*\d",re.I),
    'tension': re.compile(r"\b(?:but|however|only|left|risk|lose|loses|lost|impossible|fail|failed|eliminat\w*|time is|time.s (?:up|running)|one chance|final)\b",re.I),
    'payoff': re.compile(r"\b(?:won|winner|congratulations|did it|made it|completed|finished|revealed|result|eliminated|gave up|you win|you lose)\b",re.I),
    'reaction': re.compile(r"\b(?:wow|no way|oh my god|thank you|can.t believe|unbelievable|amazing|incredible)\b",re.I),
}


def cues(text):
    return {name: bool(pattern.search(text)) for name,pattern in PATTERNS.items()}


def boundary_score(opening, closing):
    """Reward rules at the opening and an observed outcome at the ending."""
    return 14*opening['setup'] + 18*closing['payoff'] + 8*closing['reaction']


def opening_penalty(text):
    words=re.findall(r"\b\w+\b",text)
    if PATTERNS['setup'].search(text):
        return 0
    # An isolated acknowledgment is not a self-contained opening hook.
    return 45 if len(words)<=2 else 24 if len(words)<5 else 0


def story_plan(segments, clip):
    events=[]
    text=[]
    for segment in segments:
        if segment['end']<=clip.start or segment['start']>=clip.end:
            continue
        words=segment.get('words') or []
        speech=' '.join(w['word'] for w in words if w['end']>clip.start and w['start']<clip.end) if words else segment['text']
        text.append(speech)
        # Match actual word groups for timing, not the whole long Whisper chunk.
        units=[w for w in words if w['start']<clip.end and w['end']>clip.start] if words else [dict(word=speech,start=segment['start'],end=segment['end'],source_start=segment.get('source_start',segment['start']))]
        for i,unit in enumerate(units):
            if not clip.start<=unit['start']<clip.end:
                continue
            phrase=' '.join(w['word'] for w in units[i:i+4])
            found={name:bool(pattern.match(phrase)) for name,pattern in PATTERNS.items()} if words else cues(phrase)
            kind=next((k for k in ('payoff','reaction','tension','setup') if found[k]),None)
            if kind and (not events or unit['start']-clip.start-events[-1]['time']>=2.):
                events.append(dict(kind=kind,time=round(unit['start']-clip.start,3),source_time=unit.get('source_start',unit['start']),evidence=phrase[:160]))
    full=' '.join(text)
    found=cues(full)
    mood='celebration' if found['payoff'] or found['reaction'] else 'suspense' if found['tension'] else 'drive'
    if re.search(r'\b(?:laugh|funny|joke|prank)\b',full,re.I):mood='playful'
    pulses=[]
    duration=clip.end-clip.start
    for event in events:
        t=event['time']
        if event['kind'] in ('payoff','reaction','tension') and 2.5<=t<=duration-1.7 and (not pulses or t-pulses[-1]>=6):
            pulses.append(t)
    return dict(events=events,punch_times=pulses,mood=mood,
                has_setup=found['setup'],has_payoff=found['payoff'] or found['reaction'],
                note='Dialogue cues, not verified visual events. Source order is preserved.')


def active_pulse(t, times):
    index=bisect_right(times,t)-1
    return t-times[index] if index>=0 else -1.
