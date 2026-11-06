"""Canal simulado (so software) para testes reproduziveis.

Modela o que o canal acustico costuma fazer com o sinal: atraso de inicio
(silencio antes/depois), atenuacao, desvio de fase e de frequencia da
portadora, desvio de relogio entre placas de som e ruido branco.
"""

from dataclasses import dataclass

import numpy as np
from scipy.signal import resample_poly


@dataclass
class ChannelConfig:
    lead_s: float = 0.5           # silencio antes do sinal (s)
    tail_s: float = 0.5           # silencio depois do sinal (s)
    gain: float = 0.3             # atenuacao
    phase_rad: float = 0.0        # desvio de fase da portadora
    freq_offset_hz: float = 0.0   # desvio de frequencia da portadora
    clock_ppm: float = 0.0        # desvio de relogio TX x RX (ppm)
    ebn0_db: float = None         # Eb/N0 em dB (None = sem ruido)
    seed: int = 0


def apply_channel(y, fa, rb, cfg=None):
    """Passa o sinal transmitido pelo canal simulado."""
    cfg = cfg or ChannelConfig()
    rng = np.random.default_rng(cfg.seed)
    y = np.asarray(y, dtype=float)

    # Desvio de fase/frequencia: rotaciona o sinal analitico.
    if cfg.phase_rad or cfg.freq_offset_hz:
        from scipy.signal import hilbert
        n = np.arange(len(y))
        rot = np.exp(1j * (cfg.phase_rad + 2 * np.pi * cfg.freq_offset_hz * n / fa))
        y = np.real(hilbert(y) * rot)

    # Desvio de relogio: reamostra por (1e6 + ppm)/1e6.
    if cfg.clock_ppm:
        up = int(round(1e6 + cfg.clock_ppm))
        y = resample_poly(y, up, 1000000)

    sig = y * cfg.gain
    out = np.concatenate([np.zeros(int(cfg.lead_s * fa)), sig,
                          np.zeros(int(cfg.tail_s * fa))])

    if cfg.ebn0_db is not None:
        # Energias em unidades discretas (soma de amostras ao quadrado):
        # Eb = energia por bit do trecho com sinal; ruido branco real com
        # densidade N0/2 tem variancia N0/2 por amostra nessas unidades.
        eb = np.sum(sig ** 2) / (len(sig) / fa * rb)
        n0 = eb / 10 ** (cfg.ebn0_db / 10)
        out = out + rng.normal(0, np.sqrt(n0 / 2), len(out))
    return out


def flip_bits(bits, positions):
    """Inverte bits em posicoes escolhidas (injecao controlada de erros)."""
    bits = np.array(bits, dtype=np.uint8, copy=True)
    bits[list(positions)] ^= 1
    return bits
