"""Real CC0 field recordings (BigSoundBank, Joseph Sardin) cut into seamless loops.

  0954 Passage of a combine harvester #2 -> threshing loop, drum spin-up / run-down
  0132 Tractor #1 (plowing, close pass)   -> diesel under load
  1145 Diesel engine, steady idle         -> idle
  0967 Diesel engine start and stop       -> start / stop one-shots
Usage: python real_sounds.py <srcdir> <outdir>"""
import os
import subprocess
import sys
import urllib.request
import wave

import numpy as np
from scipy.signal import butter, sosfiltfilt

SR = 44100
SRC, OUT = sys.argv[1], sys.argv[2]
os.makedirs(SRC, exist_ok=True)
os.makedirs(OUT, exist_ok=True)


def load(num):
    ogg = os.path.join(SRC, num + '.ogg')
    if not os.path.exists(ogg):
        req = urllib.request.Request('https://bigsoundbank.com/UPLOAD/ogg/%s.ogg' % num, headers={'User-Agent': 'Mozilla/5.0'})
        with open(ogg, 'wb') as f:
            f.write(urllib.request.urlopen(req, timeout=60).read())
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', ogg, '-ac', '1', '-ar', str(SR), '-f', 's16le', '-'],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, '<i2').astype(np.float64) / 32768.0


def band(x, lo=None, hi=None):
    if lo:
        x = sosfiltfilt(butter(4, lo, 'highpass', fs=SR, output='sos'), x)
    if hi:
        x = sosfiltfilt(butter(4, hi, 'lowpass', fs=SR, output='sos'), x)
    return x


def db_env(x, win=0.1):
    n = int(win * SR)
    k = len(x) // n
    return 20 * np.log10(np.sqrt((x[:k * n].reshape(k, n) ** 2).mean(1)) + 1e-9), n


def steadiest(x, length, t0, t1):
    """Start of the loud window with the least level fluctuation (no pass-by swell)."""
    env, n = db_env(band(x, lo=40))
    L = int(length * SR / n)
    i0, i1 = int(t0 * SR / n), min(int(t1 * SR / n), len(env) - L)
    scores = [np.std(env[i:i + L]) - 0.05 * env[i:i + L].mean() for i in range(i0, i1)]
    return (i0 + int(np.argmin(scores))) * n / SR


def make_loop(seg, xf=0.7):
    """Equal-power crossfade of the tail into the head, so the loop point is inaudible."""
    X = int(xf * SR)
    out = seg[:-X].copy()
    t = np.linspace(0, np.pi / 2, X)
    out[:X] = seg[:X] * np.sin(t) + seg[-X:] * np.cos(t)
    return out


def level(x, peak=0.85):
    return x / (np.max(np.abs(x)) + 1e-9) * peak


def fade(x, fin, fout):
    x = x.copy()
    a, b = int(fin * SR), int(fout * SR)
    if a:
        x[:a] *= np.linspace(0, 1, a)
    if b:
        x[-b:] *= np.linspace(1, 0, b)
    return x


def varispeed(x, r0, r1, seconds):
    """Playback rate ramps r0 -> r1 (drum spin-up / run-down)."""
    rate = np.linspace(r0, r1, int(seconds * SR))
    pos = np.cumsum(rate)
    pos = pos[pos < len(x) - 1]
    return np.interp(pos, np.arange(len(x)), x)


def save(name, x):
    wav = os.path.join(OUT, name + '.wav')
    with wave.open(wav, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype('<i2').tobytes())
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', wav, '-c:a', 'libvorbis', '-q:a', '6',
                    os.path.join(OUT, name + '.ogg')], check=True)
    os.remove(wav)
    print('%-18s %5.1f s  %6.1f dBFS rms' % (name, len(x) / SR, 20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-9)))


def ease(n):
    return np.sin(np.linspace(0, np.pi / 2, n)) ** 2


# threshing: combine close pass - drum and fan whine, straw walkers, sieves, belts
x = load('0954')
t = steadiest(x, 11.0, 112.0, 140.0)
loop = level(make_loop(band(x[int(t * SR):int((t + 11.7) * SR)], lo=45)))
save('threshing_loop', loop)
spin = np.tile(loop, 2)
up = varispeed(spin, 0.35, 1.0, 3.5)
save('threshing_start', level(up * ease(len(up)), 0.8))
down = varispeed(spin, 1.0, 0.25, 3.0)
save('threshing_stop', level(fade(down * ease(len(down))[::-1], 0.0, 0.2), 0.8))

# diesel under load: tractor plowing, approach before the pass-by
x = load('0132')
t = steadiest(x, 9.0, 3.0, 24.0)
save('engine_load_loop', level(make_loop(band(x[int(t * SR):int((t + 9.7) * SR)], lo=30, hi=9000))))

# idle
x = load('1145')
t = steadiest(x, 8.0, 2.0, 33.0)
save('engine_idle_loop', level(make_loop(band(x[int(t * SR):int((t + 8.7) * SR)], lo=30)), 0.75))

# start / stop one-shots
x = load('0967')
env, n = db_env(band(x, lo=40), 0.02)
on = np.argmax(env > env.max() - 30) * n / SR
save('motor_start', level(fade(x[int(max(0.0, on - 0.1) * SR):int((on + 2.8) * SR)], 0.01, 0.6), 0.85))
end = np.where(env > env.max() - 25)[0][-1] * n / SR
save('motor_stop', level(fade(x[int(max(0.0, end - 1.4) * SR):int(min(len(x) / SR, end + 0.9) * SR)], 0.05, 0.4), 0.8))
