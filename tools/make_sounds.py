"""Builds the mod's sound loops from CC0 field recordings (BigSoundBank, Joseph Sardin).

Usage: python tools/make_sounds.py <out_dir>   (needs ffmpeg; downloads sources into build/snd_src)

Sources (all CC0):
  0954 Passage of a combine harvester #2  -> threshing/work loop (combine drives at walking pace,
       so doppler shift over the chosen window is negligible)
  0132 Tractor #1 (plowing, close pass)   -> engine under load loop
  1145 Iveco Daily diesel, steady idle    -> engine idle layer
  0967 Diesel engine start and stop       -> motor start / stop one-shots
"""
import os
import subprocess
import sys
import urllib.request

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfiltfilt

OUT = sys.argv[1] if len(sys.argv) > 1 else "build/sounds"
SRC = os.path.join(os.path.dirname(OUT.rstrip("/")) or ".", "snd_src")
SR = 44100
os.makedirs(OUT, exist_ok=True)
os.makedirs(SRC, exist_ok=True)


def load(num):
    ogg = os.path.join(SRC, num + ".ogg")
    wav = os.path.join(SRC, num + ".wav")
    if not os.path.exists(ogg):
        req = urllib.request.Request("https://bigsoundbank.com/UPLOAD/ogg/%s.ogg" % num,
                                     headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as r, open(ogg, "wb") as f:
            f.write(r.read())
    if not os.path.exists(wav):
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", ogg, "-ac", "1", "-ar", str(SR), wav], check=True)
    x, _ = sf.read(wav)
    return x


def band(x, lo=None, hi=None):
    if lo and hi:
        sos = butter(4, [lo, hi], "bandpass", fs=SR, output="sos")
    elif lo:
        sos = butter(4, lo, "highpass", fs=SR, output="sos")
    else:
        sos = butter(4, hi, "lowpass", fs=SR, output="sos")
    return sosfiltfilt(sos, x)


def steadiest(x, length, t0, t1):
    """Start (s) of the window within [t0, t1] with the most constant loudness and high level."""
    best, best_t = None, t0
    hop = 0.25
    t = t0
    while t + length <= t1:
        seg = x[int(t * SR):int((t + length) * SR)]
        blocks = seg[:len(seg) // 2205 * 2205].reshape(-1, 2205)
        db = 20 * np.log10(np.sqrt((blocks ** 2).mean(1)) + 1e-9)
        score = db.std() - 0.15 * db.mean()
        if best is None or score < best:
            best, best_t = score, t
        t += hop
    return best_t


def make_loop(seg, xfade=1.0):
    """Seamless loop: the tail is crossfaded (equal power) into the head."""
    n = int(xfade * SR)
    body = seg[:-n].copy()
    tail = seg[-n:]
    ramp = np.linspace(0, np.pi / 2, n)
    body[:n] = body[:n] * np.sin(ramp) + tail * np.cos(ramp)
    return body


def level(x, peak=0.89):
    # soft-limit, then normalise
    x = np.tanh(x / (np.abs(x).max() + 1e-9) * 1.3)
    return x / np.abs(x).max() * peak


def fade(x, fin=0.02, fout=0.3):
    x = x.copy()
    a, b = int(fin * SR), int(fout * SR)
    x[:a] *= np.linspace(0, 1, a)
    x[-b:] *= np.linspace(1, 0, b)
    return x


def save(name, x):
    wav = os.path.join(OUT, name + ".wav")
    sf.write(wav, x.astype(np.float32), SR, subtype="PCM_16")
    ogg = os.path.join(OUT, name + ".ogg")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", wav, "-c:a", "libvorbis", "-q:a", "6", ogg],
                   check=True)
    os.remove(wav)
    print("%-26s %.1f s" % (name + ".ogg", len(x) / SR))


# threshing: combine close pass, drum/sieve whine + straw walkers + belts
x = load("0954")
t = steadiest(x, 11.0, 112.0, 140.0)
seg = band(x[int(t * SR):int((t + 11.0) * SR)], lo=45)
save("bizon_threshing_loop", level(make_loop(seg)))

# engine under load: tractor plowing, close pass
x = load("0132")
t = steadiest(x, 9.0, 3.0, 24.0)
seg = band(x[int(t * SR):int((t + 9.0) * SR)], lo=30, hi=9000)
save("bizon_engine_load_loop", level(make_loop(seg)))

# idle: steady diesel idle
x = load("1145")
t = steadiest(x, 8.0, 2.0, 33.0)
seg = band(x[int(t * SR):int((t + 8.0) * SR)], lo=30)
save("bizon_engine_idle_loop", level(make_loop(seg), 0.8))

# start / stop one-shots from the diesel start-stop recording
x = load("0967")
db = 20 * np.log10(np.abs(band(x, lo=40)) + 1e-9)
on = np.argmax(db > db.max() - 30) / SR
save("bizon_motor_start", level(fade(x[int(max(0, on - 0.1) * SR):int((on + 2.6) * SR)], 0.01, 0.6), 0.85))
off_env = np.convolve(np.abs(x), np.ones(2205) / 2205, "same")
end = len(x) / SR - 0.2
while end > 5 and off_env[int(end * SR)] < off_env.max() * 0.2:
    end -= 0.05
save("bizon_motor_stop", level(fade(x[int((end - 1.2) * SR):int((end + 0.8) * SR)], 0.05, 0.4), 0.8))
