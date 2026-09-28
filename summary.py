"""Local, sentence-aligned story assembly and source-to-output time mapping.

This is an explainable editorial heuristic, not a visual reasoning model.
Every span retains source provenance; omitted footage never supplies captions.
"""
from dataclasses import replace
from collections import Counter
import math
import re
from selector import Clip, sentences_from_transcript, challenge_signal
from story import cues, opening_penalty

STOPWORDS = set('about after again almost already another anything around because before behind being could doing every everyone everything first going gonna great having honestly itself little looks maybe myself never nothing people really right should something start starting still their there these thing things think those through today trying until video videos wanna watch where which while whole would years thank thanks incredible amazing believe chance'.split())
AD = re.compile(r'\b(?:sponsor\w*|promo code|subscribe|discount code|merch|co[\s-]*founders?|buy yours|scan the qr|go online|link (?:below|in|or))\b|\w+\s*\.com', re.I)
SETUP = re.compile(r'\b(?:by the end|going to (?:turn|build|give|survive)|our goal|the goal|we (?:will|are building)|i (?:will|am going)|dedicating)\b', re.I)
OUTCOME = re.compile(r'\b(?:look at (?:it|this|that) now|we (?:built|gave|raised|created|turned)|fully functioning|all (?:that.s|that is) left|after (?:a year|months|weeks)|finally|in the end)\b', re.I)
TURNING_POINT = re.compile(r'\b(?:one chance|fail\w*|risk\w*|eliminat\w*|impossible|broke|broken|lost|running out)\b', re.I)


def validate_spans(clip, duration, max_duration=360):
    if len(clip.spans) > 64:
        raise ValueError('A summary can contain at most 64 source sections.')
    if clip.spans and clip.crop_keyframes:
        raise ValueError('Summary sections use automatic framing; manual crop paths are for individual clips.')
    previous = -1.
    for span in clip.spans:
        start, end = span['start'], span['end']
        if not all(math.isfinite(v) for v in (start, end)) or not 0 <= start < end <= duration+.05 or start < previous:
            raise ValueError('Summary sections must be ordered, non-overlapping and within the source.')
        previous = end
    if not 0 < clip.duration <= max_duration+.001:
        raise ValueError(f'Edited duration must be between 0 and {max_duration} seconds.')


def timeline(clip, transcript):
    """Return an output-time clip and transcript without mutating source data."""
    if not clip.spans:
        return clip, transcript
    output, offset = [], 0.
    for span in clip.spans:
        a, b = span['start'], span['end']
        for segment in transcript:
            if segment['end'] <= a or segment['start'] >= b:
                continue
            words = [dict(w, start=max(a, w['start'])-a+offset,
                          end=min(b, w['end'])-a+offset, source_start=max(a, w['start']))
                     for w in segment.get('words', []) if w['start'] < b and w['end'] > a]
            # Untimed text is safe only when the entire segment was retained.
            text = ' '.join(w['word'].strip() for w in words) if segment.get('words') else segment['text'] if segment['start'] >= a and segment['end'] <= b else ''
            if text:
                output.append(dict(start=max(a, segment['start'])-a+offset,
                                   end=min(b, segment['end'])-a+offset,
                                   source_start=max(a, segment['start']), text=text, words=words))
        offset += b-a
    return replace(clip, start=0., end=offset, spans=[], crop_keyframes=[]), output


def select_summaries(transcript, count, target, duration, *, minimum=0):
    """Cover the whole source with setup/development/outcome, never pad count.

    Additional stories require unused setup AND outcome evidence. Chronology is
    preserved; temporal coverage and duplicate penalties limit repetitive reels.
    """
    sentences = [s for s in sentences_from_transcript(transcript)
                 if 0 <= s['start'] < s['end'] <= duration+.05]
    if not sentences:
        return []
    if duration <= target:
        return [Clip(0, duration, sentences[0]['text'][:68], 1,
                     'Source already fits target; retained complete context')]
    candidates = []
    # Repeated concrete vocabulary anchors a summary to this video's subject.
    tokens_for = lambda text: set(re.findall(r'\b[a-z]{5,}\b', text.lower()))-STOPWORDS
    frequency = Counter(token for s in sentences for token in tokens_for(s['text']))
    topics = {token for token, n in frequency.most_common(18) if n > 1}
    ads = [(s['start']-12, s['end']+18) for s in sentences if AD.search(s['text'])]
    maximum = max(4., min(30. if target > 120 else 18., target/4))
    for i, sentence in enumerate(sentences):
        if sentence['end']-sentence['start'] > maximum:
            continue
        text, end = sentence['text'], sentence['end']
        # Include adjacent speech as context; never jump across a long silence.
        for following in sentences[i+1:i+(8 if target > 120 else 4)]:
            if following['end']-sentence['start'] > maximum or following['start']-end > 1.2:
                break
            text += ' '+following['text']
            end = following['end']
        if AD.search(text) or any(sentence['start'] < b and end > a for a, b in ads):
            continue
        flags = cues(text)
        flags['setup'] |= bool(SETUP.search(text))
        flags['payoff'] |= bool(OUTCOME.search(text))
        tokens = tokens_for(text)
        relevance = len(tokens & topics)
        dependent = bool(re.match(r'^(?:and|but|yeah|yep|wow|thank|he|she|they|it|that|oh|sure|okay)\b', sentence['text'], re.I))
        score = (challenge_signal(text)+8*flags['tension']+4*flags['reaction']
                 +16*bool(TURNING_POINT.search(text))+9*relevance-12*dependent-opening_penalty(sentence['text'])*.4)
        candidates.append(dict(start=sentence['start'], end=end, text=text, flags=flags,
                               tokens=tokens, score=score, relevance=relevance))
    used, results = [], []
    overlaps = lambda a, b: a['start'] < b['end'] and a['end'] > b['start']
    for number in range(count):
        available = [c for c in candidates if not any(overlaps(c, s) for s in used)]
        setups = [c for c in available if c['flags']['setup'] and c['start'] < duration*.4]
        endings = [c for c in available if c['flags']['payoff'] and c['start'] > duration*.6]
        if not endings:
            endings = [c for c in available if c['flags']['reaction'] and c['start'] > duration*.75 and c['relevance']]
        if not setups or not endings:
            break
        first = max(setups, key=lambda c: c['score']+60*bool(SETUP.search(c['text']))+100*(1-c['start']/duration))
        last = max(endings, key=lambda c: c['score']+45*c['end']/duration)
        chosen = [first, last]
        if overlaps(first, last) or sum(c['end']-c['start'] for c in chosen) > target:
            break
        remaining = target-sum(c['end']-c['start'] for c in chosen)
        while remaining >= 2 and len(chosen) < 64:
            options = [c for c in available if c['start'] >= first['end'] and c['end'] <= last['start']
                       and c['end']-c['start'] <= remaining and c['score'] >= 12
                       and (not topics or c['relevance'] > 0 or TURNING_POINT.search(c['text']))
                       and (any(c['flags'].values()) or c['relevance'] >= 3)
                       and not any(overlaps(c, s) for s in chosen)]
            if not options:
                break
            def rank(c):
                distance = min(abs(c['start']-s['start']) for s in chosen)/duration
                repetition = max(len(c['tokens'] & s['tokens'])/max(1, len(c['tokens'] | s['tokens'])) for s in chosen)
                return c['score']+40*distance-25*repetition
            best = max(options, key=rank)
            chosen.append(best)
            remaining -= best['end']-best['start']
        chosen.sort(key=lambda c: c['start'])
        if len(chosen) < 3 or target-remaining < max(minimum, min(20, target*.5)):
            break
        spans = [dict(start=c['start'], end=c['end'], evidence=c['text'],
                      role='setup' if c is first else 'outcome' if c is last else 'development') for c in chosen]
        clip = Clip(spans[0]['start'], spans[-1]['end'], first['text'][:68],
                    round(sum(c['score'] for c in chosen)/len(chosen), 2),
                    'Whole-source dialogue summary: chronological setup, developments and outcome; review inferred story links', spans=spans)
        validate_spans(clip, duration)
        results.append(clip)
        used.extend(chosen)
    return results
