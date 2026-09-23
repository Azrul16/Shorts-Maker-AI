"""ASS captions with word timing, short readable lines, and karaoke highlighting."""
from pathlib import Path


def timestamp(seconds):
    cs = max(0, round(seconds * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02}:{cs // 100 % 60:02}.{cs % 100:02}"


def safe(text):
    return text.replace("\\", " ").replace("{", "(").replace("}", ")").replace("\n", " ")


def write_captions(path, segments, start, end):
    words = []
    for segment in segments:
        if segment["end"] <= start or segment["start"] >= end:
            continue
        timed = segment.get("words")
        if not timed:
            tokens = segment["text"].split()
            step = (segment["end"] - segment["start"]) / max(1, len(tokens))
            timed = [{"word": t, "start": segment["start"] + i * step, "end": segment["start"] + (i + 1) * step} for i, t in enumerate(tokens)]
        words.extend(w for w in timed if w["end"] > start and w["start"] < end and w["word"].strip())
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,62,&H004AEAD4,&H00FFFFFF,&H00101018,&H80000000,-1,0,0,0,100,100,0,0,1,4,2,2,80,80,300,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    groups, group = [], []
    for word in words:
        if group and (len(group) >= 5 or len(" ".join(w["word"] for w in group)) + len(word["word"]) > 30 or word["start"] - group[-1]["end"] > .6):
            groups.append(group)
            group = []
        group.append(word)
    if group:
        groups.append(group)
    for group in groups:
        begin = max(start, group[0]["start"])
        finish = min(end, group[-1]["end"])
        if finish <= begin:
            continue
        text = []
        cursor = begin
        for word in group:
            gap = max(0, word["start"] - cursor)
            if gap > .02:
                text.append("{\\k%d} " % round(gap * 100))
            length = max(.01, min(end, word["end"]) - max(start, word["start"]))
            text.append("{\\k%d}%s " % (round(length * 100), safe(word["word"])))
            cursor = word["end"]
        lines.append(f"Dialogue: 0,{timestamp(begin-start)},{timestamp(finish-start)},Default,,0,0,0,,{''.join(text).strip()}")
    Path(path).write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
