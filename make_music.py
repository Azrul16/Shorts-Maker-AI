"""Compose two original instrumental loops using synthesized tones (no samples)."""
from pathlib import Path
import wave
import numpy as np

RATE = 48000


def compose(style, path):
    bpm = 90 if style == 'ambient' else 104
    beat = 60 / bpm
    duration = 32 * beat
    count = round(duration * RATE)
    audio = np.zeros((count, 2), dtype=np.float64)
    rng = np.random.default_rng(42)

    def add(signal, start, gain=1, pan=0):
        offset = round(start * RATE)
        positions = (offset + np.arange(len(signal))) % count
        audio[positions, 0] += signal * gain * np.sqrt((1-pan)/2)
        audio[positions, 1] += signal * gain * np.sqrt((1+pan)/2)

    def note(midi, seconds, pad=False):
        t = np.arange(round(seconds * RATE)) / RATE
        frequency = 440 * 2 ** ((midi-69)/12)
        if pad:
            envelope = np.minimum(1, t / .35) * np.minimum(1, (seconds-t) / .7)
            return (np.sin(2*np.pi*frequency*t) + .22*np.sin(2*np.pi*frequency*2.002*t)) * envelope
        envelope = (1-np.exp(-t*90)) * np.exp(-t*3.4) * np.minimum(1, (seconds-t)/.04)
        return (np.sin(2*np.pi*frequency*t) + .3*np.sin(2*np.pi*frequency*2*t)) * envelope

    # Cmaj7 - Am7 - Fmaj7 - G6, repeated with a small melodic variation.
    chords = [(48, 55, 59, 64), (45, 52, 55, 60), (41, 48, 52, 57), (43, 50, 55, 59)]
    for bar in range(8):
        chord = chords[bar % 4]
        start = bar * 4 * beat
        for j, pitch in enumerate(chord):
            add(note(pitch + 12, 4 * beat + .45, True), start, .065, (j-1.5)*.35)
        for j in range(8):
            pitch = chord[(j + (bar // 4)) % 4] + 24
            add(note(pitch, beat * 1.8), start + j * beat / 2, .12 if j % 2 == 0 else .07, .35 if j % 2 else -.35)
        for j in (0, 2):
            add(note(chord[0]-12, beat*1.7), start+j*beat, .22)
        if style == 'beat':
            for j in range(4):
                t = np.arange(round(.24*RATE))/RATE
                kick = np.sin(2*np.pi*(48*t + 2*(1-np.exp(-t*35)))) * np.exp(-t*20) * np.minimum(1, t*800)
                add(kick, start+j*beat, .19 if j % 2 == 0 else .09)
            for j in range(8):
                noise = rng.normal(0, 1, round(.055*RATE))
                noise = np.concatenate(([0], np.diff(noise)))
                noise *= np.exp(-np.arange(len(noise))/RATE*85)
                add(noise, start+j*beat/2, .011, .2)
    audio *= .78 / max(.01, np.max(np.abs(audio)))
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), 'wb') as output:
        output.setnchannels(2)
        output.setsampwidth(2)
        output.setframerate(RATE)
        output.writeframes((audio*32767).astype('<i2').tobytes())


if __name__ == '__main__':
    compose('ambient', Path('assets/music/soft_ambient.wav'))
    compose('beat', Path('assets/music/light_beat.wav'))
