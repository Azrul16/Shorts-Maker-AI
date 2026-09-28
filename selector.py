"""Offline transcript scoring with sentence boundaries and no overlapping clips."""
from collections import Counter
from dataclasses import dataclass, asdict, field
import math
import re
from story import cues, boundary_score, opening_penalty


@dataclass
class Clip:
    start: float
    end: float
    title: str
    score: float
    reason: str
    crop_keyframes: list = field(default_factory=list)
    caption_style: str = 'classic'
    effects: str = 'off'
    spans: list = field(default_factory=list)

    @property
    def duration(self):
        return sum(s['end']-s['start'] for s in self.spans) if self.spans else self.end-self.start

    def to_dict(self):
        return asdict(self)


def sentences_from_transcript(segments):
    """Split at word-level punctuation instead of treating a Whisper chunk as a sentence."""
    sentences, current = [], None
    for segment in segments:
        words = segment.get("words") or []
        units = [{"start": w['start'], "end": w['end'], "text": w['word'].strip()} for w in words]
        if not units:
            units = [dict(segment)]
        for unit in units:
            text = unit['text'].strip()
            if not text:
                continue
            if current and unit['start']-current['end'] > .9:
                sentences.append(current)
                current = None
            if current is None:
                current = {'start': unit['start'], 'end': unit['end'], 'text': text}
            else:
                current['end'] = unit['end']
                current['text'] += ' ' + text
            ending = bool(re.search(r'[.!?。！？]["\u201d\u2019]*$', text))
            abbreviation = text.lower() in {'mr.', 'mrs.', 'ms.', 'dr.', 'st.', 'vs.', 'etc.'}
            if (ending and not abbreviation) or current['end']-current['start'] > 25:
                sentences.append(current)
                current = None
    if current:
        sentences.append(current)
    return sentences


def editorial_score(first, last, text, length, target, topics):
    opening = first['text'].lower().strip()
    closing = last['text'].lower().strip()
    words = re.findall(r'\b\w+\b', text.lower())
    hook = bool(re.match(r"^(?:here.s (?:why|how|what)|(?:why|how|what if|did you know|imagine|the (?:secret|truth|biggest)|most people|you (?:can|should|need)))\b", opening))
    greeting = bool(re.match(r"^(?:how.s it going|how are you|what.s up|hello|hey|hi|okay|ok|alright|all right)\b", opening))
    if greeting:
        hook = False
    dependent = bool(re.match(r"^(?:and|but|so|then|because|also|anyway|once|oh|yeah|yes|no|he|she|they|it|that|this|these|those|his|her|their|we start)\b", opening))
    payoff = bool(re.search(r"\b(?:finally|changed|saved|learned|discovered|realized|thank\w*|dream\w*|happy|happiest|excited|first time|never .{0,45}before|the result|that.s why|incredible|amazing)\b", text.lower()))
    ad = bool(re.search(r"\b(?:sponsor\w*|subscribe|promo code|discount code|link (?:in|below)|merch|download (?:the|this) app)\b", text.lower()))
    incomplete_end = not re.search(r'[.!?。！？]["\u201d\u2019]*$', closing)
    dangling_end = bool(re.search(r"(?:here.s (?:why|how)|let me (?:show|explain)|watch this|check this out)[.!]*$", closing))
    dangling_end = dangling_end or bool(re.match(r"^(?:this is|meet|next|now let.s)\b", closing))
    density = len(words)/max(length, 1)
    coverage = sum(min(1, topics.get(w, 0)) for w in set(words))
    score = 45 + 16*hook + 15*payoff - 22*dependent - 40*ad
    score -= 22*greeting
    score += min(10, coverage) + 7*(not incomplete_end)
    score -= 18*incomplete_end + 16*dangling_end + abs(length-target)*.4
    score -= max(0, 1.25-density)*15 + max(0, density-4.5)*8
    reason = 'Word-aligned boundaries and standalone context'
    if hook:
        reason += '; opening hook'
    if payoff:
        reason += '; reaction or payoff'
    return round(score, 1), reason


def challenge_signal(text):
    text = text.lower()
    stakes = bool(re.search(r'\b(challenge|last to (?:leave|stop)|survive|prize|dollars?|minutes? left|time limit)\b|\$\s*\d',text))
    payoff = bool(re.search(r'\b(won|winner|wins|eliminated|reveal|finished|completed|made it|did it)\b',text))
    return 10*stakes+8*payoff


def select_clips(segments, count=3, target=40, duration=None, category=None):
    if not segments:
        raise ValueError("No speech was found in this video.")
    duration = duration or segments[-1]["end"]
    sentences = sentences_from_transcript(segments)
    if not sentences:
        raise ValueError("No usable speech was found.")
    keywords = Counter(re.findall(r"\b[a-z]{5,}\b", " ".join(s["text"].lower() for s in sentences)))
    for word in ("there", "their", "about", "would", "could", "going", "these", "those", "which", "really", "thing", "think"):
        keywords.pop(word, None)
    topics = {w: math.log1p(n) for w, n in keywords.most_common(30)}
    sentence_tokens = [set(re.findall(r"\b[a-z]{5,}\b", s["text"].lower())) for s in sentences]
    sentence_cues = [cues(s["text"]) for s in sentences]
    opening_penalties = [opening_penalty(s["text"]) for s in sentences]
    candidates = []
    tokens = {}
    minimum, maximum = max(12, target * .65), min(120, target * 1.35)
    for i, first in enumerate(sentences):
        title = re.sub(r"\s+", " ", first["text"]).strip()
        if len(title) > 68:
            title = title[:65].rsplit(" ", 1)[0] + "…"
        window = []
        window_tokens = set()
        for j in range(i, len(sentences)):
            last = sentences[j]
            window.append(last)
            window_tokens.update(sentence_tokens[j])
            length = last["end"] - first["start"]
            if length > maximum:
                break
            if length < minimum:
                continue
            text = " ".join(s["text"] for s in window)
            score, reason = editorial_score(first, last, text, length, target, topics)
            bonus = challenge_signal(text) + boundary_score(sentence_cues[i], sentence_cues[j])
            score += bonus-opening_penalties[i]
            if bonus:
                reason += '; challenge setup, tension or payoff'
            if sentence_cues[i]['setup'] and sentence_cues[j]['payoff']:
                reason += '; setup-to-outcome story'
            candidate = Clip(max(0, first["start"] - .08), min(duration, last["end"] + .12), title, score, reason)
            candidates.append(candidate)
            tokens[id(candidate)] = window_tokens.copy()
    if not candidates:
        if duration <= maximum:
            return [Clip(0, duration, sentences[0]["text"][:68], 0, "Short source: full video")]
        raise ValueError("Could not find a complete speech window. Try a longer clip duration.")
    selected = []
    penalties = {id(c): 0. for c in candidates}
    while candidates and len(selected) < count:
        best = max(candidates, key=lambda c: c.score-penalties[id(c)])
        selected.append(best)
        candidates = [c for c in candidates if c.end <= best.start or c.start >= best.end]
        if len(selected) == count:
            break
        b = tokens[id(best)]
        for candidate in candidates:
            a = tokens[id(candidate)]
            intersection = len(a & b)
            similarity = intersection/max(1, len(a)+len(b)-intersection)
            separation = min(abs(candidate.end-best.start), abs(best.end-candidate.start))
            penalty = 10*similarity + max(0, 1-separation/max(target*2, 1))*7
            penalties[id(candidate)] = max(penalties[id(candidate)], penalty)
    return sorted(selected, key=lambda c: c.start)
