"""Offline transcript scoring with sentence boundaries and no overlapping clips."""
from collections import Counter
from dataclasses import dataclass, asdict
import math
import re


@dataclass
class Clip:
    start: float
    end: float
    title: str
    score: float
    reason: str

    def to_dict(self):
        return asdict(self)


def complete_selection(clips, duration, count, target):
    """Fill ranking gaps; repartition only when greedy picks block the count."""
    if count < 1 or target <= 0 or duration <= 0:
        raise ValueError("Count, duration and target length must be positive.")
    minimum = min(12, target)
    achievable = min(count, max(1, int(duration / minimum)))
    length = min(target, duration / achievable)
    selected = sorted(clips[:achievable], key=lambda c: c.start)
    if len(selected) == achievable:
        return selected
    boundaries = [(0, selected[0].start)] if selected else [(0, duration)]
    if selected:
        boundaries += [(a.end, b.start) for a, b in zip(selected, selected[1:])]
        boundaries += [(selected[-1].end, duration)]
    for start, end in boundaries:
        while end - start >= length - .001 and len(selected) < achievable:
            selected.append(Clip(start, start + length, f"Scene at {int(start)//60:02}:{int(start)%60:02}", 0, "Additional distinct scene to meet requested count"))
            start += length
    if len(selected) < achievable:
        # Sparse dialogue and greedy overlapping candidates must not silently
        # reduce a long movie to one short. Keep every window distinct.
        selected = []
        span = duration / achievable
        for i in range(achievable):
            start = i * span
            choices = [c for c in clips if c.start >= start and c.end <= (i+1)*span]
            if choices:
                selected.append(max(choices, key=lambda c: c.score))
            else:
                selected.append(Clip(start, min(duration, start+length), f"Scene {i+1}", 0, "Distributed scene fallback to meet requested count"))
    return sorted(selected, key=lambda c: c.start)


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


def select_clips(segments, count=3, target=40, duration=None):
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
    candidates = []
    tokens = {}
    minimum, maximum = max(12, target * .65), min(90, target * 1.35)
    for i, first in enumerate(sentences):
        window = []
        for last in sentences[i:]:
            window.append(last)
            length = last["end"] - first["start"]
            if length > maximum:
                break
            if length < minimum:
                continue
            text = " ".join(s["text"] for s in window)
            score, reason = editorial_score(first, last, text, length, target, topics)
            title = re.sub(r"\s+", " ", first["text"]).strip()
            if len(title) > 68:
                title = title[:65].rsplit(" ", 1)[0] + "…"
            candidate = Clip(max(0, first["start"] - .08), min(duration, last["end"] + .12), title, score, reason)
            candidates.append(candidate)
            tokens[id(candidate)] = set(re.findall(r'\b[a-z]{5,}\b', text.lower()))
    if not candidates:
        if duration <= maximum:
            return [Clip(0, duration, sentences[0]["text"][:68], 0, "Short source: full video")]
        raise ValueError("Could not find a complete speech window. Try a longer clip duration.")
    selected = []
    while candidates and len(selected) < count:
        def diverse_score(candidate):
            penalty = 0
            a = tokens[id(candidate)]
            for other in selected:
                b = tokens[id(other)]
                similarity = len(a & b)/max(1, len(a | b))
                separation = min(abs(candidate.end-other.start), abs(other.end-candidate.start))
                penalty = max(penalty, 10*similarity + max(0, 1-separation/max(target*2, 1))*7)
            return candidate.score-penalty
        best = max(candidates, key=diverse_score)
        selected.append(best)
        candidates = [c for c in candidates if c.end <= best.start or c.start >= best.end]
    return sorted(selected, key=lambda c: c.start)
