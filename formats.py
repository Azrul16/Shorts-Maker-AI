"""Shared output profiles; dimensions stay even for H.264 encoding."""
PROFILES = {
    'reel': dict(maximum=120, minimum=0, music=.50, label='Reel'),
    'summary': dict(maximum=360, minimum=240, music=.18, label='Summary video'),
}


def output_size(media, quality, output_type='reel', layout='source'):
    if output_type == 'reel' or layout == 'vertical':
        return (1080, 1920) if quality == 1920 else (720, 1280)
    long_edge = 1920 if quality == 1920 else 1280
    if layout == 'landscape':
        return long_edge, long_edge*9//16
    if layout != 'source':
        raise ValueError('Unknown summary picture format.')
    w, h = media['width'], media['height']
    if w <= 0 or h <= 0:
        raise ValueError('Invalid source dimensions.')
    bounds = (long_edge, long_edge*9/16) if w >= h else (long_edge*9/16, long_edge)
    scale = min(bounds[0]/w, bounds[1]/h)
    return max(2, round(w*scale/2)*2), max(2, round(h*scale/2)*2)
