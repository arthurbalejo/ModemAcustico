"""Parametros do enlace (Marco 1) e do receptor.

Valores tirados do codigo-base do professor (tx.m, transmissor.m,
receptor_2.m). Os campos marcados como "extra" nao existem no codigo-base
e podem ser desligados para reproduzir o comportamento original.
"""

from dataclasses import dataclass


# ----------------------------------------------------------------------
# Camada fisica (tx.m / transmissor.m)
# ----------------------------------------------------------------------
RB = 100          # taxa de bits (bit/s)
FP = 2000         # frequencia da portadora (Hz)
FA = 8000         # frequencia de amostragem (Hz)
ROLLOFF = 0.5     # fator de decaimento do cosseno levantado
RC_DELAY = 3      # atraso de grupo do filtro RC, em simbolos (padrao do rcosine.m)


@dataclass
class TxConfig:
    rb: float = RB
    fp: float = FP
    fa: int = FA
    rolloff: float = ROLLOFF
    rc_delay: int = RC_DELAY
    # soundsc() do Octave escala o sinal para [-1, 1] antes de tocar.
    # Aqui a escala e feita na saida do transmissor (pico = amplitude).
    amplitude: float = 0.9


@dataclass
class RxConfig:
    rb: float = RB
    fp: float = FP
    fa: int = FA

    # Laco de Costas (receptor_1.m / receptor_2.m)
    costas_order: int = 64        # fle
    costas_cutoff: float = 0.001  # fir1(fle, 0.001)
    costas_mu: float = 0.03       # mu

    # Sincronizacao de simbolo cedo-tarde (receptor_2.m)
    el_d: int = 1                 # d (cedo e tarde, em amostras)
    el_err: float = 0.01          # erro permitido

    # Sincronizacao de quadro (correlacao com o SFD)
    sfd_threshold: float = 0.9    # fracao de len(SFD) para aceitar o pico

    # --- extras (nao estao no codigo-base) ---
    # Filtro passa-faixa na entrada (aparece no diagrama da proposta).
    bandpass: bool = True
    bandpass_bw: float = 1000.0   # largura total da faixa em torno de FP (Hz)
    # Normaliza o nivel do sinal recebido (o passo mu do Costas e o limiar
    # el_err dependem da amplitude).
    agc: bool = True
    # Passa-baixas depois do misturador: remove o termo em 2*FP antes da
    # sincronizacao de simbolo e da decisao. None = automatico:
    # corte = RB e 2*Fa/RB + 1 coeficientes (dois simbolos). Cortes mais
    # largos (300 Hz) deixam passar ruido que faz o cedo-tarde escorregar.
    lowpass: bool = True
    lowpass_cutoff: float = None   # Hz
    lowpass_taps: int = None

    @classmethod
    def professor(cls, **kw):
        """Configuracao identica ao receptor_2.m (sem os extras)."""
        base = dict(bandpass=False, agc=False, lowpass=False)
        base.update(kw)
        return cls(**base)
