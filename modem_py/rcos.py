"""Porte de rcosine.m e rcosflt.m (opcao 'filter') do codigo-base."""

import math

import numpy as np
from scipy.signal import lfilter


def rcosine(fd, fs, r=0.5, delay=3):
    """Filtro FIR cosseno levantado normal, como rcosine(Fd, Fs, 'default', r).

    Retorna os coeficientes normalizados para soma 1 (igual ao original).
    Comprimento: 2*delay*fs/fd + 1 coeficientes.
    """
    td = 1.0 / fd
    ts = 1.0 / fs
    n = np.arange(-math.floor(delay * td / ts), math.ceil(delay * td / ts) + 1)
    t = n * ts
    num = np.zeros(len(t))
    for i, ti in enumerate(t):
        rr = r
        if abs(r * ti / td) == 0.5:
            # mesmo truque do original para evitar a divisao por zero
            rr = r - 1.0 / 2 ** 23
        num[i] = (np.sinc(ti / td) * math.cos(math.pi * rr * ti / td)
                  / (1 - (2 * rr * ti / td) ** 2))
    return num / num.sum()


def rcosflt_filter(x, fd, fs, num):
    """Equivalente a rcosflt(x, Fd, Fs, 'filter', num).

    Sobreamostra x por fs/fd (um impulso por simbolo), filtra com num e
    devolve len(x)*fs/fd amostras. Como no original, o final do filtro e
    cortado: os ultimos simbolos ficam incompletos (por isso o quadro
    termina com um preambulo extra).
    """
    ratio = fs / fd
    if abs(ratio - round(ratio)) > 1e-9:
        raise ValueError("Fs/Fd deve ser inteiro")
    ratio = int(round(ratio))
    x = np.asarray(x, dtype=float).ravel()
    xx = np.zeros(len(x) * ratio)
    xx[::ratio] = x
    return lfilter(num, 1.0, xx)
