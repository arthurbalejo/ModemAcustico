"""Transmissor BPSK (porte de transmissor.m).

Interface para as outras camadas:
    audio = transmit_bits(payload_bits)      # bits -> amostras de audio
A camada de erros (CRC/Hamming) e o TDM entregam bits aqui; o quadro
(PRE + SFD + LEN + PRE), a formatacao de pulso e a modulacao ficam por conta
deste modulo.
"""

import math

import numpy as np

from .config import TxConfig
from .framing import build_frame, text_to_bits
from .rcos import rcosine, rcosflt_filter


def bit_rate_adjusted(rb, fa):
    """RB_f = Fa/floor(Fa/RB): taxa ajustada para amostras/simbolo inteiro."""
    return fa / math.floor(fa / rb)


def modulate(frame_bits, cfg=None):
    """Bits do quadro -> sinal BPSK em banda passante (sem normalizar).

    Etapas de transmissor.m: codificacao polar, filtro RC, modulacao.
    Retorna (passband, baseband).
    """
    cfg = cfg or TxConfig()
    bits = np.asarray(frame_bits, dtype=np.uint8).ravel()
    symbols = np.array([-1.0, 1.0])[bits]           # s = [-1, 1]; y = s(msg+1)
    rb_f = bit_rate_adjusted(cfg.rb, cfg.fa)
    num = rcosine(rb_f, cfg.fa, cfg.rolloff, cfg.rc_delay)
    baseband = rcosflt_filter(symbols, rb_f, cfg.fa, num)
    t = np.arange(len(baseband)) / cfg.fa
    passband = baseband * np.cos(2 * np.pi * cfg.fp * t)
    return passband, baseband


def normalize(y, amplitude=0.9):
    """Escala para pico = amplitude (papel do soundsc na hora de tocar)."""
    peak = np.max(np.abs(y)) if len(y) else 0.0
    return y * (amplitude / peak) if peak > 0 else y


def transmit_bits(payload_bits, cfg=None):
    """Ponto de entrada do transmissor: payload em bits -> audio em [-1, 1]."""
    cfg = cfg or TxConfig()
    passband, _ = modulate(build_frame(payload_bits), cfg)
    return normalize(passband, cfg.amplitude)


def transmit_text(text, cfg=None):
    """Igual ao tx.m: texto -> bits (LSB primeiro) -> audio."""
    return transmit_bits(text_to_bits(text), cfg)
