"""Synthesised sounds for the mod (numpy -> WAV -> OGG via ffmpeg).

Physically motivated: a 4-stroke inline six fires 3 times per revolution in the
order 1-5-3-6-2-4; every firing is a damped thump + bark + knock + injector tick
with per-cylinder spread and jitter, shaped by exhaust/body resonances.  All
filtering is circular (FFT), so the loops repeat without a seam.
Usage: python make_sounds.py <outdir>"""
import os
import subprocess
import sys
import wave
import numpy as np

SR = 44100
OUT = sys.argv[1] if len(sys.argv) > 1 else 'build/sounds'
os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(1956)


def band(x, lo, hi, order=2.0):
    f = np.fft.rfftfreq(len(x), 1 / SR)
    h = 1 / (1 + (lo / np.maximum(f, 1e-3)) ** (2 * order)) / (1 + (f / hi) ** (2 * order))
    return np.fft.irfft(np.fft.rfft(x) * h, len(x))


def resonate(x, freqs, q=6.0, gain=1.0):
    f = np.fft.rfftfreq(len(x), 1 / SR)
    h = np.ones_like(f)
    for fc in freqs:
        h += gain / (1 + (q * (f / fc - fc / np.maximum(f, 1e-3))) ** 2)
    return np.fft.irfft(np.fft.rfft(x) * h, len(x))


def pulse_train(n, firing_times, amps, rpm_at, kind='run'):
    out = np.zeros(n)
    for t0, a in zip(firing_times, amps):
        i0 = int(t0 * SR)
        L = int(0.06 * SR)
        tau = np.arange(L) / SR
        rpm = rpm_at(t0)
        load = 1.0 if kind == 'run' else 0.8
        ph = rng.uniform(0, 6.28)
        p = (np.sin(2 * np.pi * (85 + rpm * 0.012) * tau) * np.exp(-tau / 0.02) * 1.0
             + np.sin(2 * np.pi * (240 + rpm * 0.03) * tau + ph) * np.exp(-tau / 0.011) * 0.55 * load
             + band(rng.standard_normal(L), 1400, 4200) * np.exp(-tau / 0.0045) * 0.45
             + band(rng.standard_normal(L), 5000, 9000) * np.exp(-tau / 0.0012) * 0.18)
        idx = (i0 + np.arange(L)) % n
        np.add.at(out, idx, a * p)
    return out


def engine_loop(rpm=1000.0, seconds=4.0):
    cycle = 120.0 / rpm
    ncyc = max(1, round(seconds / cycle))
    n = int(round(ncyc * cycle * SR))
    gains = [1.0, 0.92, 1.06, 0.95, 1.03, 0.9]
    times, amps = [], []
    for c in range(ncyc):
        for k in range(6):
            times.append((c * cycle + k * cycle / 6) * (1 + rng.normal(0, 0.002)))
            amps.append(gains[k] * (1 + rng.normal(0, 0.07)))
    x = pulse_train(n, times, amps, lambda t: rpm)
    fire = rpm / 60 * 3
    rumble = band(rng.standard_normal(n), 40, 220) * (1 + 0.6 * np.sin(2 * np.pi * fire * np.arange(n) / SR))
    mech = band(rng.standard_normal(n), 900, 5000) * 0.06
    whine = 0.015 * np.sin(2 * np.pi * (rpm / 60 * 23) * np.arange(n) / SR)
    x = x + 0.25 * rumble / np.std(rumble) * np.std(x) * 0.5 + mech * np.std(x) + whine * np.std(x) * 10
    x = resonate(x, [115, 330, 780], q=4.0, gain=1.2)
    return x


def threshing_loop(seconds=6.0):
    n = int(seconds * SR)
    t = np.arange(n) / SR
    pink = np.fft.irfft(np.fft.rfft(rng.standard_normal(n)) / np.maximum(np.sqrt(np.fft.rfftfreq(n, 1 / SR)), 1), n)
    x = band(pink, 120, 7000) / np.std(pink)
    drum = sum(np.sin(2 * np.pi * 147 * h * t * (1 + 0.002 * np.sin(2 * np.pi * 0.5 * t))) / h for h in (1, 2, 3, 4)) * 0.35
    beater = sum(np.sin(2 * np.pi * 211 * h * t) / (h * 1.5) for h in (1, 2, 3)) * 0.18
    clatter = np.zeros(n)
    period = 1 / 3.33
    k = 0
    while k * period / 2 < seconds:
        i0 = int(k * period / 2 * SR)
        L = int(0.05 * SR)
        tau = np.arange(L) / SR
        idx = (i0 + np.arange(L)) % n
        np.add.at(clatter, idx, band(rng.standard_normal(L), 400, 2500) * np.exp(-tau / 0.012) * (1.0 if k % 2 else 0.8))
        k += 1
    sieve = band(rng.standard_normal(n), 1200, 3500) * (0.6 + 0.4 * np.sin(2 * np.pi * 5.0 * t)) * 0.4
    belts = band(rng.standard_normal(n), 60, 300) * (1 + 0.5 * np.sin(2 * np.pi * 22 * t)) * 0.5
    return x + drum + beater + clatter * 1.2 + sieve + belts


def engine_ramp(rpm_from, rpm_to, dur, starter=False, tail=0.0):
    n = int((dur + tail) * SR)
    times, amps = [], []
    t, k = 0.0, 0
    gains = [1.0, 0.92, 1.06, 0.95, 1.03, 0.9]

    def rpm_at(tt):
        a = min(1.0, tt / dur)
        return rpm_from + (rpm_to - rpm_from) * (a ** 0.7 if rpm_to > rpm_from else a)
    while t < dur:
        rpm = max(rpm_at(t), 60.0)
        strength = 1.0 if rpm_to > rpm_from else max(0.0, 1 - t / dur) ** 0.5
        if starter and t < 0.9:
            strength = 0.25 if rng.random() > 0.35 else 0.0
        if strength > 0:
            times.append(t)
            amps.append(gains[k % 6] * strength * (1 + rng.normal(0, 0.12)))
        t += 20.0 / rpm
        k += 1
    x = pulse_train(n, times, amps, rpm_at, kind='start')
    tt = np.arange(n) / SR
    if starter:
        st = np.clip(1 - tt / 1.3, 0, 1)
        f = 170 + 90 * np.clip(tt / 1.0, 0, 1)
        comp = 0.6 + 0.4 * np.sign(np.sin(2 * np.pi * 7.5 * tt))
        whine = np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * 0.12 + band(rng.standard_normal(n), 2000, 6000) * 0.05
        x += whine * st * comp * np.std(x[:int(0.9 * SR)] + 1e-3) * 12
        puff = band(rng.standard_normal(n), 60, 800) * np.exp(-np.maximum(tt - 1.0, 0) / 0.25) * (tt > 1.0)
        x += puff * 0.3 * np.std(x)
    x = resonate(x, [115, 330, 780], q=4.0, gain=1.2)
    return x


def write(name, x, fade=0.0):
    x = x / (np.max(np.abs(x)) + 1e-9) * 0.7
    if fade:
        f = int(fade * SR)
        x[-f:] *= np.linspace(1, 0, f)
    wav = os.path.join(OUT, name + '.wav')
    with wave.open(wav, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype('<i2').tobytes())
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', wav, '-c:a', 'libvorbis', '-q:a', '5',
                    os.path.join(OUT, name + '.ogg')], check=True)
    os.remove(wav)


if __name__ == '__main__':
    write('engine_run', engine_loop(1000.0, 4.0))
    write('engine_idle', engine_loop(850.0, 3.0))
    write('engine_start', np.concatenate([engine_ramp(150, 900, 2.2, starter=True), engine_loop(900.0, 0.6)]), fade=0.2)
    write('engine_stop', engine_ramp(850, 40, 1.6, tail=0.5), fade=0.3)
    write('threshing_loop', threshing_loop(6.0))
    ramp = threshing_loop(3.0)
    env = np.linspace(0, 1, len(ramp)) ** 1.5
    write('threshing_start', ramp * env)
    write('threshing_stop', ramp * env[::-1], fade=0.3)
    print('sounds ->', OUT)
