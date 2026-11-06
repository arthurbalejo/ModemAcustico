"""Sequencias de teste conhecidas e comparacao de bits."""

import numpy as np


def prbs7(n, seed=0x7F):
    """PRBS-7 (x^7 + x^6 + 1). Mesma sequencia em qualquer maquina."""
    state = seed & 0x7F
    if state == 0:
        raise ValueError("semente nao pode ser zero")
    out = np.zeros(n, dtype=np.uint8)
    for i in range(n):
        bit = ((state >> 6) ^ (state >> 5)) & 1
        state = ((state << 1) | bit) & 0x7F
        out[i] = bit
    return out


def compare_bits(sent, received):
    """Compara bit a bit. Bits faltando no recebido contam como erro."""
    sent = np.asarray(sent, dtype=np.uint8).ravel()
    received = np.asarray(received, dtype=np.uint8).ravel()
    n = min(len(sent), len(received))
    err_pos = np.flatnonzero(sent[:n] != received[:n]).tolist()
    missing = max(0, len(sent) - len(received))
    n_err = len(err_pos) + missing
    return dict(n_sent=int(len(sent)), n_received=int(len(received)),
                n_errors=int(n_err), missing=int(missing),
                ber=float(n_err / len(sent)) if len(sent) else 0.0,
                error_positions=err_pos, equal=bool(n_err == 0 and len(sent) == len(received)))


def bits_to_str(bits):
    return "".join("1" if b else "0" for b in np.asarray(bits).ravel())


def str_to_bits(s):
    s = "".join(c for c in s if c in "01")
    return np.array([int(c) for c in s], dtype=np.uint8)
