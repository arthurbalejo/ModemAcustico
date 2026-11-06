"""Entrada e saida de audio: placa de som (sounddevice) e arquivos WAV."""

import time

import numpy as np
from scipy.io import wavfile


def write_wav(path, y, fa):
    """Grava WAV PCM 16 bits mono (como audiowrite do rx.m)."""
    y = np.clip(np.asarray(y, dtype=float), -1.0, 1.0)
    wavfile.write(path, int(fa), (y * 32767).astype(np.int16))


def read_wav(path, fa=None):
    """Le WAV e devolve amostras em [-1, 1] (primeiro canal).

    Se fa for dado e o arquivo tiver outra taxa, reamostra para fa.
    """
    fs, data = wavfile.read(path)
    if data.ndim > 1:
        data = data[:, 0]
    if np.issubdtype(data.dtype, np.integer):
        data = data / float(np.iinfo(data.dtype).max + 1)
    data = data.astype(float)
    if fa is not None and fs != fa:
        from math import gcd
        from scipy.signal import resample_poly
        g = gcd(int(fs), int(fa))
        data = resample_poly(data, int(fa) // g, int(fs) // g)
        fs = fa
    return data, int(fs)


def _sd():
    try:
        import sounddevice as sd
    except (ImportError, OSError) as exc:
        raise RuntimeError("sounddevice/PortAudio indisponivel: %s" % exc)
    return sd


def play(y, fa, device=None):
    """Toca o sinal e espera terminar (soundsc + play)."""
    sd = _sd()
    sd.play(np.asarray(y, dtype=np.float32), int(fa), device=device)
    sd.wait()


def record(seconds, fa, device=None):
    """Grava 'seconds' segundos mono (record do Octave)."""
    sd = _sd()
    y = sd.rec(int(seconds * fa), samplerate=int(fa), channels=1,
               dtype="float32", device=device)
    sd.wait()
    return y[:, 0].astype(float)


def record_until_signal(seconds, fa, level=0.1, max_tries=20, device=None,
                        verbose=True):
    """Laco do rx.m: grava blocos ate o pico passar de 'level' (NS_min)."""
    for i in range(max_tries):
        y = record(seconds, fa, device)
        ns = float(np.max(np.abs(y))) if len(y) else 0.0
        if verbose:
            print("captura %d: nivel de sinal = %.3f" % (i + 1, ns))
        if ns >= level:
            return y, ns
    raise RuntimeError("nenhum sinal acima de %.3f em %d capturas" % (level, max_tries))


def play_and_record(y, fa, lead_s=0.5, tail_s=1.0, device=None):
    """Toca e grava ao mesmo tempo (uma maquina so: alto-falante -> microfone)."""
    sd = _sd()
    y = np.asarray(y, dtype=np.float32)
    out = np.concatenate([np.zeros(int(lead_s * fa), np.float32), y,
                          np.zeros(int(tail_s * fa), np.float32)])
    rec = sd.playrec(out, samplerate=int(fa), channels=1, dtype="float32",
                     device=device)
    sd.wait()
    time.sleep(0.05)
    return rec[:, 0].astype(float)
