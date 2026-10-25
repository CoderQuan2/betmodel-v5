#!/usr/bin/env python3
"""Generate BetFi Xii's four UI sounds (v12.1; startup added
v12.4) — pure stdlib.

The app has exactly four sounds, all quiet by design (the shell
caps playback volume at SOUND_VOLUME = 0.30 on top of these
already-low gains):

  tick.wav     ~50 ms single sine blip — navigation + primary taps
  confirm.wav  ~120 ms, two gentle rising tones — Protected Slip
  golden.wav   ~250 ms soft four-note chime arpeggio, the quietest
               of the three — a pull lands its first GOLDEN bet
  startup.wav  ~700 ms soft rising two-note sweep with a quiet
               chime tail — once per cold start (v12.4). Written
               at 11025 Hz so the longer sweep still lands under
               the 25 KB asset cap; its gains sit at or below the
               golden chime's.

22050 Hz mono 16-bit WAV (11025 Hz for startup.wav); exponential
decay envelopes with short attack ramps so nothing clicks. Each
file lands well under 25 KB.

Run:  python tools/make_sounds.py
Writes into ../assets/sounds/ (relative to this file).
"""
import math
import os
import struct
import wave

SR = 22050
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "..", "assets", "sounds")


def _tone(freq, dur_s, gain, decay=6.0, sr=SR):
    """One enveloped sine note: 5 ms attack ramp, exp decay."""
    n = int(sr * dur_s)
    attack = max(1, int(sr * 0.005))
    out = []
    for i in range(n):
        t = i / sr
        env = math.exp(-decay * t)
        if i < attack:
            env *= i / attack
        out.append(gain * env * math.sin(2 * math.pi * freq * t))
    return out


def _write(name, samples, sr=SR):
    path = os.path.join(OUT_DIR, name)
    os.makedirs(OUT_DIR, exist_ok=True)
    frames = b"".join(
        struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32767))
        for s in samples)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(frames)
    print(f"{name}: {len(frames) + 44} bytes, "
          f"{len(samples) / sr * 1000:.0f} ms")


def main():
    # tick: one soft blip
    _write("tick.wav", _tone(880.0, 0.050, 0.25))
    # confirm: two gentle tones rising (660 -> 990), 60 ms each
    _write("confirm.wav",
           _tone(660.0, 0.060, 0.22) + _tone(990.0, 0.060, 0.22))
    # golden: quiet four-note arpeggio (C5 E5 G5 C6), ~62 ms each
    golden = []
    for f in (523.25, 659.25, 783.99, 1046.50):
        golden += _tone(f, 0.0625, 0.15, decay=5.0)
    _write("golden.wav", golden)
    # startup (v12.4): a soft rising two-note sweep (C5 -> G5,
    # slow decays so the notes bloom rather than blip) with a
    # quiet C6 chime tail — ~700 ms total, gains at or below
    # the golden chime's 0.15 peak, at half sample rate to
    # stay under the 25 KB cap.
    startup = (_tone(523.25, 0.22, 0.13, decay=2.5, sr=11025)
               + _tone(783.99, 0.22, 0.12, decay=2.5, sr=11025)
               + _tone(1046.50, 0.26, 0.09, decay=6.0, sr=11025))
    _write("startup.wav", startup, sr=11025)


if __name__ == "__main__":
    main()
