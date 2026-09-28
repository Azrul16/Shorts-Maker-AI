"""Transparent export checks, not a virality score or an accuracy claim."""
from pathlib import Path
from projects import atomic_json


def export_report(video, media, rendered, duration, height):
    width = 1080 if height == 1920 else 720
    checks = {
        'vertical_dimensions': media['width']==width and media['height']==height,
        'duration': abs(media['duration']-duration) <= .5,
        'audio_stream': media.get('has_audio',True),
    }
    if media.get('video_codec'):
        checks['h264_video'] = media['video_codec']=='h264'
    if media.get('audio_codec'):
        checks['aac_audio'] = media['audio_codec']=='aac'
    if media.get('fps'):
        checks['30_fps'] = abs(media['fps']-30)<.1
    warnings = []
    if rendered.get('dark_samples',0)>=2:
        warnings.append('Very dark frames were sampled. Review the source, fades and crop.')
    samples = rendered.get('face_samples',0)
    report = dict(technical_pass=all(checks.values()),checks=checks,warnings=warnings,
                  tracking=rendered.get('tracking'),
                  face_observation_coverage=rendered.get('face_detections',0)/samples if samples else None,
                  note='Face observations do not measure editorial quality. Review composition and source rights before posting.')
    path = Path(video).with_suffix('.quality.json')
    atomic_json(path,report)
    text_path = Path(video).with_suffix('.quality.txt')
    text = ['EXPORT CHECKS']+[f'{"PASS" if ok else "FAIL"}: {name.replace("_"," ")}' for name,ok in checks.items()]
    if report['face_observation_coverage'] is not None:
        text += [f"Face observations: {report['face_observation_coverage']:.0%} of frames (not an accuracy measurement)"]
    text += ['']+warnings+['',report['note']]
    text_path.write_text('\n'.join(text),encoding='utf-8')
    return {**report,'file':str(text_path),'json':str(path)}
