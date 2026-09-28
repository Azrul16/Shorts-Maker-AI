"""Cheap deterministic finishing effects; no extra video pass or random flashes."""
import math
from story import active_pulse


def punch_zoom(t,duration,mode='off',cues=()):
    if mode!='energetic' or t<0 or t>=duration:
        return 1.
    # Smooth in and out without sudden zoom jumps.
    amplitude = .09
    phase = active_pulse(t,cues)
    if t<2.5 or phase<0 or phase>=1.2 or t-phase+1.2>duration-.5:
        return 1.
    return 1.+amplitude*math.sin(math.pi*phase/1.2)**2
