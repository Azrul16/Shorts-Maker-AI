"""Offline transcript scoring with sentence boundaries and no overlapping clips."""
from collections import Counter
from dataclasses import dataclass, asdict
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


def select_clips(segments, count=3, target=40, duration=None):
    if not segments:
        raise ValueError("No speech was found in this video.")
    duration = duration or segments[-1]["end"]
    sentences, current = [], None
    for segment in segments:
        text = segment["text"].strip()
        if not text:
            continue
        if current and segment["start"] - current["end"] > 1.2:
            sentences.append(current)
            current = None
        if current is None:
            current = {"start": segment["start"], "end": segment["end"], "text": text}
        else:
            current["end"] = segment["end"]
            current["text"] += " " + text
        if re.search(r'[.!?。！？]["\u201d\u2019]*$', text) or current["end"] - current["start"] > 18:
            sentences.append(current)
            current = None
    if current:
        sentences.append(current)
    if not sentences:
        raise ValueError("No usable speech was found.")
    keywords = Counter(re.findall(r"\b[a-z]{5,}\b", " ".join(s["text"].lower() for s in sentences)))
    for word in ("there", "their", "about", "would", "could", "going", "these", "those", "which", "really", "thing", "think"):
        keywords.pop(word, None)
    topics = set(w for w, n in keywords.most_common(25))
    candidates = []
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
            lower = text.lower()
            words = re.findall(r"\b\w+\b", lower)
            hook = bool(re.search(r"\b(why|how|imagine|secret|mistake|never|surpris\w*|what if|the truth|here.s|first time)\b", first["text"].lower()))
            weak_start = bool(re.match(r"^(and|but|so|then|because|also|anyway)\b", first["text"], re.I))
            density = len(words) / max(length, 1)
            score = 40 + 12 * hook - 10 * weak_start + min(12, len(set(words) & topics))
            score += 8 * bool(re.search(r"[.!?。！？]$", last["text"]))
            score += 5 * bool(re.search(r"\d|\b(result|learn|build|change|finally|discover)\w*", lower))
            score -= abs(length - target) * .55 + max(0, 1.3 - density) * 12
            title = re.sub(r"\s+", " ", first["text"]).strip()
            if len(title) > 68:
                title = title[:65].rsplit(" ", 1)[0] + "…"
            reason = "Sentence boundaries, topic relevance and speech density" + ("; opening hook" if hook else "")
            candidates.append(Clip(max(0, first["start"] - .1), min(duration, last["end"] + .15), title, round(score, 1), reason))
    if not candidates:
        if duration <= maximum:
            return [Clip(0, duration, sentences[0]["text"][:68], 0, "Short source: full video")]
        raise ValueError("Could not find a complete speech window. Try a longer clip duration.")
    selected = []
    for candidate in sorted(candidates, key=lambda c: c.score, reverse=True):
        if all(candidate.end <= other.start or candidate.start >= other.end for other in selected):
            selected.append(candidate)
            if len(selected) == count:
                break
    return sorted(selected, key=lambda c: c.start)
