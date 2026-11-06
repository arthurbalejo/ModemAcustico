"""Receptor BPSK (porte de receptor_2.m).

Interface para as outras camadas:
    payload_bits, info = receive_bits(audio)  # audio -> bits
Etapas (mesma ordem do receptor_2.m, com os extras opcionais de RxConfig):
    [passa-faixa] -> [AGC] -> laco de Costas -> demodulacao -> [passa-baixas]
    -> sincronizacao de simbolo cedo-tarde -> decisao -> correlacao com SFD
"""

import numpy as np
from scipy.signal import butter, firwin, sosfiltfilt

from .config import RxConfig
from .framing import bits_to_text, parse_frame


def bandpass(y, cfg):
    lo = cfg.fp - cfg.bandpass_bw / 2
    hi = cfg.fp + cfg.bandpass_bw / 2
    sos = butter(4, [lo, hi], btype="bandpass", fs=cfg.fa, output="sos")
    return sosfiltfilt(sos, y)


def agc(y):
    """Normaliza pelo percentil 99.9 de |y| (robusto a estalos isolados)."""
    ref = np.percentile(np.abs(y), 99.9) if len(y) else 0.0
    return y / ref if ref > 0 else y


def costas_loop(y, cfg):
    """Laco de Costas do receptor_1.m/receptor_2.m.

    Para cada amostra k, multiplica por sin/cos da portadora local, filtra
    os dois ramos com o FIR fir1(fle, 0.001) (ultimas fle+1 amostras) e
    atualiza theta(k+1) = theta(k) - mu * lpfs * lpfc.
    """
    n = len(y)
    fle = cfg.costas_order
    h = firwin(fle + 1, cfg.costas_cutoff)  # mesmo projeto do fir1 (Hamming)
    hr = h[::-1]                             # fliplr(h)
    w = 2 * np.pi * cfg.fp / cfg.fa
    theta = np.zeros(n)
    zs = np.zeros(n + fle)                   # buffers com fle zeros iniciais
    zc = np.zeros(n + fle)
    mu = cfg.costas_mu
    for k in range(n - 1):
        ph = w * k + theta[k]
        zs[k + fle] = 2 * y[k] * np.sin(ph)
        zc[k + fle] = 2 * y[k] * np.cos(ph)
        lpfs = hr @ zs[k:k + fle + 1]
        lpfc = hr @ zc[k:k + fle + 1]
        theta[k + 1] = theta[k] - mu * lpfs * lpfc
    return theta


def lowpass(y, cfg):
    cutoff = cfg.lowpass_cutoff or cfg.rb
    taps = cfg.lowpass_taps or 2 * int(np.ceil(cfg.fa / cfg.rb)) + 1
    h = firwin(taps, cutoff, fs=cfg.fa)
    return np.convolve(y, h, mode="same")    # fase zero (FIR simetrico)


def early_late(yf, cfg):
    """Sincronizacao de simbolo cedo-tarde do receptor_2.m (indices em 0).

    Compara |yf(t-d)| e |yf(t+d)| e anda uma amostra para o lado maior.
    Retorna os indices de amostragem escolhidos.
    """
    st = int(np.ceil(cfg.fa / cfg.rb))
    d = cfg.el_d
    err = cfg.el_err
    n = len(yf)
    t = st - 1                               # t = st no Octave (indice 1)
    idx = []
    while t + d < n:
        dif = abs(yf[t - d]) - abs(yf[t + d])
        if dif > err:
            t -= 1
        elif dif < -err:
            t += 1
        idx.append(t)
        t += st
        # No original os indices que sobram ficam valendo 1 e acabam
        # amostrados; aqui eles sao simplesmente descartados.
        if t > n - st:
            break
    return np.array(idx, dtype=int)


def demodulate(yrx, cfg=None):
    """Audio -> bits decididos (todos, antes da sincronizacao de quadro).

    Retorna (bits, diag) com os sinais intermediarios para as figuras.
    """
    cfg = cfg or RxConfig()
    y = np.asarray(yrx, dtype=float).ravel()
    if cfg.bandpass:
        y = bandpass(y, cfg)
    if cfg.agc:
        y = agc(y)
    theta = costas_loop(y, cfg)
    k = np.arange(len(y))
    ph = 2 * np.pi * cfg.fp / cfg.fa * k + theta
    i_branch = y * np.cos(ph)
    q_branch = -y * np.sin(ph)
    if cfg.lowpass:
        i_branch = lowpass(i_branch, cfg)
        q_branch = lowpass(q_branch, cfg)
    si = early_late(i_branch, cfg)
    samples = i_branch[si]
    bits = (samples > 0).astype(np.uint8)
    diag = dict(input=y, theta=theta, i=i_branch, q=q_branch,
                sample_index=si, samples=samples, samples_q=q_branch[si])
    return bits, diag


def receive_bits(yrx, cfg=None):
    """Ponto de entrada do receptor: audio -> (payload em bits, info).

    info['ok'] e False quando o pico da correlacao com o SFD fica abaixo
    do limiar (equivale ao aviso 'Muitos erros para decodificar os dados').
    """
    cfg = cfg or RxConfig()
    bits, diag = demodulate(yrx, cfg)
    info = parse_frame(bits, cfg.sfd_threshold)
    info["diag"] = diag
    info["raw_bits"] = bits
    return info["payload"], info


def receive_text(yrx, cfg=None):
    payload, info = receive_bits(yrx, cfg)
    return bits_to_text(payload), info
