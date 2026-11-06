"""Quadro do enlace basico (transmissor.m / receptor_2.m).

Quadro: PRE | SFD | LEN (1 byte) | PAYLOAD (LEN bytes) | PRE

- PRE: 10 uns seguidos de 15 pares "1 0" (40 bits).
- SFD: 32 bits fixos do codigo-base.
- LEN: numero de bytes do payload (0..255).
- Bytes em bits LSB primeiro, como de2bi/bi2de do Octave.
"""

import numpy as np

PRE = np.array([1] * 10 + [1, 0] * 15, dtype=np.uint8)
SFD = np.array([1, 1, 0, 0, 1, 1, 1, 0, 0, 0, 1, 1, 1, 1, 0, 0,
                0, 0, 1, 1, 1, 0, 0, 0, 1, 1, 0, 0, 1, 0, 1, 0], dtype=np.uint8)
MAX_BYTES = 255


def bytes_to_bits(values):
    """de2bi(values, 8) linha a linha, LSB primeiro."""
    values = np.asarray(values, dtype=np.uint8).ravel()
    return ((values[:, None] >> np.arange(8)) & 1).astype(np.uint8).ravel()


def bits_to_bytes(bits):
    """bi2de(reshape(bits, 8, [])'), LSB primeiro. Ignora bits que sobram."""
    bits = np.asarray(bits, dtype=np.uint8).ravel()
    n = len(bits) // 8
    b = bits[:n * 8].reshape(n, 8).astype(np.uint16)
    return (b << np.arange(8)).sum(axis=1).astype(np.uint8)


def text_to_bits(text):
    return bytes_to_bits(np.frombuffer(text.encode("latin-1"), dtype=np.uint8))


def bits_to_text(bits):
    return bytes(bits_to_bytes(bits)).decode("latin-1", errors="replace")


def pad_to_bytes(bits):
    """Completa com zeros ate um multiplo de 8 bits."""
    bits = np.asarray(bits, dtype=np.uint8).ravel()
    extra = (-len(bits)) % 8
    return np.concatenate([bits, np.zeros(extra, dtype=np.uint8)])


def build_frame(payload_bits):
    """Monta o quadro completo a partir dos bits de payload.

    Se o payload nao for multiplo de 8, e completado com zeros; o receptor
    devolve os bits completados (a camada de cima sabe o tamanho real).
    """
    payload = pad_to_bytes(payload_bits)
    nbytes = len(payload) // 8
    if nbytes > MAX_BYTES:
        raise ValueError("payload maior que %d bytes" % MAX_BYTES)
    return np.concatenate([PRE, SFD, bytes_to_bits([nbytes]), payload, PRE])


def sfd_correlation(bits):
    """Correlacao de SFD (+-1) com os bits decididos (+-1), so sobreposicao total.

    corr[k] corresponde ao SFD comecando no bit k.
    """
    x = np.asarray(bits, dtype=float) * 2 - 1
    s = SFD.astype(float) * 2 - 1
    if len(x) < len(s):
        return np.zeros(0)
    return np.correlate(x, s, mode="valid")


def parse_frame(bits, threshold=0.9):
    """Sincronizacao de quadro e extracao do payload (final de receptor_2.m).

    Retorna dict com payload (bits), nbytes, posicao do SFD, pico da
    correlacao, se houve inversao de polaridade e se o pico passou do limiar.
    """
    bits = np.asarray(bits, dtype=np.uint8).ravel()
    corr = sfd_correlation(bits)
    if len(corr) == 0:
        return dict(ok=False, payload=np.zeros(0, np.uint8), nbytes=0,
                    sfd_index=-1, peak=0.0, inverted=False, corr=corr,
                    complete=False, bits=bits)
    k = int(np.argmax(np.abs(corr)))
    peak = float(corr[k])
    inverted = peak < 0
    if inverted:
        # ambiguidade de fase de 180 graus do BPSK
        bits = 1 - bits
    ok = abs(peak) >= threshold * len(SFD)
    start = k + len(SFD)
    header = bits[start:start + 8]
    nbytes = int(bits_to_bytes(header)[0]) if len(header) == 8 else 0
    payload = bits[start + 8:start + 8 + 8 * nbytes]
    return dict(ok=bool(ok), payload=payload, nbytes=nbytes, sfd_index=k,
                peak=peak, inverted=bool(inverted), corr=corr,
                complete=len(payload) == 8 * nbytes, bits=bits)
