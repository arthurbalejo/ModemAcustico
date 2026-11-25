"""Multiplexacao por divisao de tempo (TDM) de dois fluxos de bits.

Fica entre a camada de erros (fec.py) e o enlace (transmit_bits /
receive_bits). Nao mexe na modulacao: so organiza os bits do payload.

Ordem no sistema (Marco 2, secao 5):
    TX: fluxo A, fluxo B -> CRC-8 -> Hamming (7,4) -> MUX -> transmit_bits
    RX: receive_bits -> DEMUX -> Hamming (7,4) -> CRC-8 -> A', B'

Payload entregue ao enlace
    CABECALHO (70 bits) | SLOTS intercalados

Cabecalho (32 bits de informacao, MSB primeiro)
    n_A    12 bits  tamanho do fluxo A em bits (antes do CRC/Hamming)
    n_B    12 bits  tamanho do fluxo B em bits
    slot    4 bits  tamanho do slot menos 1 (slots de 1 a 16 bits)
    flags   4 bits  bit 0 = fluxos protegidos com CRC-8 + Hamming (7,4)
    O cabecalho recebe CRC-8 (40 bits) e Hamming (7,4) (10 blocos = 70 bits).
    O Hamming corrige 1 erro por bloco; o CRC acusa quando o cabecalho
    chegou errado mesmo assim (info['cabecalho_ok'] = False).

Slots (TDM sincrono, rodizio fixo A, B, A, B, ...)
    A cada rodada cada fluxo ocupa um slot de 'slot' bits. Quando um fluxo
    acaba, os slots dele deixam de existir e o outro segue sozinho. O ultimo
    slot de cada fluxo pode ser mais curto. O receptor refaz a mesma agenda a
    partir de n_A, n_B e slot do cabecalho, entao nao precisa de enchimento
    nem de marcador entre slots. Os bits de enchimento que o enlace acrescenta
    (payload completado ate multiplo de 8) ficam depois do ultimo slot e sao
    descartados.

    Com slot = 7 (padrao) e FEC ligado, cada slot carrega exatamente uma
    palavra Hamming (7,4). Com slot = 1 os fluxos sao intercalados bit a bit:
    uma rajada de erros no canal se espalha pelos dois fluxos e por mais
    palavras Hamming, o que ajuda a correcao.

Interface
    bits = mux(fluxo_a, fluxo_b)                 # -> transmit_bits(bits)
    a, b, info = demux(bits)                     # bits = receive_bits(...)[0]
"""

import numpy as np

from . import fec
from .framing import MAX_BYTES

N_BITS_LEN = 12                    # campo de tamanho de cada fluxo
N_BITS_SLOT = 4
N_BITS_FLAGS = 4
HEADER_INFO_BITS = 2 * N_BITS_LEN + N_BITS_SLOT + N_BITS_FLAGS   # 32
HEADER_BITS = fec.coded_length(HEADER_INFO_BITS)                 # 70
MAX_STREAM_BITS = (1 << N_BITS_LEN) - 1                          # 4095
MAX_PAYLOAD_BITS = 8 * MAX_BYTES                                 # 2040 (campo LEN)
SLOT_BITS = 7
FLAG_FEC = 1


def _bits(x):
    return np.asarray(x, dtype=np.uint8).ravel() & 1


def _uint_to_bits(value, n):
    return np.array([(value >> (n - 1 - i)) & 1 for i in range(n)], dtype=np.uint8)


def _bits_to_uint(bits):
    v = 0
    for b in bits:
        v = (v << 1) | int(b)
    return v


# ----------------------------------------------------------------------
# Cabecalho
# ----------------------------------------------------------------------
def encode_header(n_a, n_b, slot_bits, use_fec):
    """(n_A, n_B, slot, flags) -> 70 bits protegidos (CRC-8 + Hamming)."""
    for n in (n_a, n_b):
        if not 0 <= n <= MAX_STREAM_BITS:
            raise ValueError("fluxo com %d bits: limite de %d" % (n, MAX_STREAM_BITS))
    if not 1 <= slot_bits <= 1 << N_BITS_SLOT:
        raise ValueError("slot deve ter de 1 a %d bits" % (1 << N_BITS_SLOT))
    flags = FLAG_FEC if use_fec else 0
    info = np.concatenate([_uint_to_bits(n_a, N_BITS_LEN),
                           _uint_to_bits(n_b, N_BITS_LEN),
                           _uint_to_bits(slot_bits - 1, N_BITS_SLOT),
                           _uint_to_bits(flags, N_BITS_FLAGS)])
    return fec.protect(info)


def decode_header(bits):
    """70 bits -> dict(n_a, n_b, slot, fec, ok, corrigidos)."""
    msg, h = fec.recover(_bits(bits)[:HEADER_BITS], HEADER_INFO_BITS)
    if len(msg) < HEADER_INFO_BITS:
        msg = np.concatenate([msg, np.zeros(HEADER_INFO_BITS - len(msg), np.uint8)])
    i = 0
    n_a = _bits_to_uint(msg[i:i + N_BITS_LEN]); i += N_BITS_LEN
    n_b = _bits_to_uint(msg[i:i + N_BITS_LEN]); i += N_BITS_LEN
    slot = _bits_to_uint(msg[i:i + N_BITS_SLOT]) + 1; i += N_BITS_SLOT
    flags = _bits_to_uint(msg[i:i + N_BITS_FLAGS])
    return dict(n_a=n_a, n_b=n_b, slot=slot, fec=bool(flags & FLAG_FEC),
                ok=h["crc_ok"], corrigidos=h["corrigidos"])


# ----------------------------------------------------------------------
# Agenda de slots
# ----------------------------------------------------------------------
def slot_schedule(lengths, slot_bits):
    """Lista de (fluxo, inicio no fluxo, tamanho) na ordem de transmissao."""
    pos = [0] * len(lengths)
    sched = []
    while any(p < n for p, n in zip(pos, lengths)):
        for i, n in enumerate(lengths):
            if pos[i] < n:
                k = min(slot_bits, n - pos[i])
                sched.append((i, pos[i], k))
                pos[i] += k
    return sched


def slot_map(lengths, slot_bits):
    """Para cada bit apos o cabecalho, o indice do fluxo dono (0 = A, 1 = B)."""
    out = np.zeros(sum(lengths), dtype=np.uint8)
    j = 0
    for i, _, k in slot_schedule(lengths, slot_bits):
        out[j:j + k] = i
        j += k
    return out


def interleave(streams, slot_bits=SLOT_BITS):
    """Intercala os fluxos em slots (sem cabecalho)."""
    streams = [_bits(s) for s in streams]
    parts = [streams[i][p:p + k]
             for i, p, k in slot_schedule([len(s) for s in streams], slot_bits)]
    return np.concatenate(parts) if parts else np.zeros(0, np.uint8)


def deinterleave(bits, lengths, slot_bits=SLOT_BITS):
    """Inverso de interleave(): separa os fluxos pela mesma agenda."""
    bits = _bits(bits)
    out = [np.zeros(n, dtype=np.uint8) for n in lengths]
    j = 0
    for i, p, k in slot_schedule(lengths, slot_bits):
        out[i][p:p + k] = bits[j:j + k]
        j += k
    return out


# ----------------------------------------------------------------------
# MUX / DEMUX
# ----------------------------------------------------------------------
def mux_length(n_a, n_b, use_fec=True):
    """Tamanho do payload (bits) que mux() vai gerar."""
    if use_fec:
        n_a, n_b = fec.coded_length(n_a), fec.coded_length(n_b)
    return HEADER_BITS + n_a + n_b


def mux(fluxo_a, fluxo_b, slot_bits=SLOT_BITS, use_fec=True):
    """Dois fluxos de bits -> payload para transmit_bits().

    Com use_fec=True cada fluxo passa por CRC-8 e Hamming (7,4) antes de
    ser intercalado (fec.protect).
    """
    a, b = _bits(fluxo_a), _bits(fluxo_b)
    total = mux_length(len(a), len(b), use_fec)
    if total > MAX_PAYLOAD_BITS:
        raise ValueError("payload TDM com %d bits: o quadro aceita no maximo %d "
                         "(255 bytes no campo LEN)" % (total, MAX_PAYLOAD_BITS))
    header = encode_header(len(a), len(b), slot_bits, use_fec)
    if use_fec:
        a, b = fec.protect(a), fec.protect(b)
    return np.concatenate([header, interleave([a, b], slot_bits)])


def demux(bits):
    """Payload recebido -> (fluxo_a, fluxo_b, info).

    info:
      cabecalho_ok   CRC do cabecalho conferiu
      cabecalho      campos lidos (n_a, n_b, slot, fec, corrigidos)
      completo       o payload tinha todos os bits que o cabecalho anuncia
      fluxos         [info_a, info_b] com crc_ok, corrigidos, posicoes,
                     blocos (vazio se o FEC estiver desligado)
      mapa           dono de cada bit apos o cabecalho (para figuras)
    """
    bits = _bits(bits)
    h = decode_header(bits)
    lengths = [h["n_a"], h["n_b"]]
    coded = [fec.coded_length(n) for n in lengths] if h["fec"] else lengths
    body = bits[HEADER_BITS:HEADER_BITS + sum(coded)]
    complete = len(bits) >= HEADER_BITS and len(body) == sum(coded)
    if len(body) < sum(coded):
        body = np.concatenate([body, np.zeros(sum(coded) - len(body), np.uint8)])
    parts = deinterleave(body, coded, h["slot"])
    streams, infos = [], []
    for part, n in zip(parts, lengths):
        if h["fec"]:
            s, fi = fec.recover(part, n)
        else:
            s, fi = part, {}
        streams.append(s)
        infos.append(fi)
    info = dict(cabecalho_ok=h["ok"], cabecalho=h, completo=bool(complete),
                fluxos=infos, mapa=slot_map(coded, h["slot"]),
                bits_por_fluxo=coded)
    return streams[0], streams[1], info
