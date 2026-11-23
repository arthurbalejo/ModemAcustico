"""Deteccao e correcao de erros: CRC-8 e Hamming (7,4).

Todas as funcoes trabalham com arrays de bits 0/1 (numpy.uint8), na mesma
ordem em que os bits vao para o enlace (bytes com LSB primeiro, como
framing.bytes_to_bits). Nao dependem do transmissor nem do receptor.

Ordem no sistema (Marco 2, secao 5):
    TX: bits do fluxo -> crc8_encode -> hamming74_encode -> (TDM) -> enlace
    RX: enlace -> (TDM) -> hamming74_decode -> crc8_check

CRC-8
    Gerador g(x) = x^8 + x^2 + x + 1 (0x07, CRC-8/SMBUS), registro inicial
    zero, sem reflexao. O primeiro bit do array e o coeficiente de maior grau.
    O CRC (8 bits) e o resto de m(x) * x^8 dividido por g(x) e vai no fim
    da mensagem; a mensagem com o CRC tem resto zero.
    g(x) = (x + 1) * p(x), entao detecta todo numero impar de erros. Distancia
    de Hamming 4 (detecta 1, 2 e 3 erros quaisquer) ate 119 bits de dados;
    acima disso, alguns pares de erros passam. Detecta toda rajada de ate 8
    bits.

Hamming (7,4)
    Palavra c1..c7 = p1 p2 d1 p3 d2 d3 d4, com
        p1 = d1 ^ d2 ^ d4,  p2 = d1 ^ d3 ^ d4,  p3 = d2 ^ d3 ^ d4.
    A sindrome s = s1 + 2*s2 + 4*s3 e a posicao (1..7) do bit errado, ou 0.
    Distancia minima 3: corrige 1 erro por bloco. Com 2 erros no bloco a
    sindrome aponta um terceiro bit e o decodificador "corrige" errado
    (o bloco sai com 3 bits trocados); quem acusa esse caso e o CRC.
"""

import numpy as np

CRC8_POLY = 0x07          # x^8 + x^2 + x + 1 (o termo x^8 fica implicito)
CRC8_BITS = 8

# Posicoes (0..6) dos bits de dados e de paridade na palavra de 7 bits.
DATA_POS = np.array([2, 4, 5, 6])      # d1 d2 d3 d4 -> c3 c5 c6 c7
PARITY_POS = np.array([0, 1, 3])       # p1 p2 p3    -> c1 c2 c4

# Matriz geradora G (4 x 7) e de verificacao H (3 x 7), em GF(2).
# Coluna j de H = representacao binaria de j+1 (s1 na linha 0).
H = np.array([[(j + 1) >> i & 1 for j in range(7)] for i in range(3)],
             dtype=np.uint8)
G = np.array([[1, 1, 1, 0, 0, 0, 0],
              [1, 0, 0, 1, 1, 0, 0],
              [0, 1, 0, 1, 0, 1, 0],
              [1, 1, 0, 1, 0, 0, 1]], dtype=np.uint8)


def _bits(x):
    return np.asarray(x, dtype=np.uint8).ravel() & 1


# ----------------------------------------------------------------------
# CRC-8
# ----------------------------------------------------------------------
def crc8(bits):
    """CRC-8 (g = 0x07) dos bits, devolvido como 8 bits (maior grau primeiro)."""
    reg = 0
    for b in _bits(bits):
        fb = ((reg >> 7) & 1) ^ int(b)
        reg = (reg << 1) & 0xFF
        if fb:
            reg ^= CRC8_POLY
    return np.array([(reg >> (7 - i)) & 1 for i in range(8)], dtype=np.uint8)


def crc8_encode(bits):
    """Mensagem + CRC: acrescenta os 8 bits do CRC no fim."""
    bits = _bits(bits)
    return np.concatenate([bits, crc8(bits)])


def crc8_check(bits_with_crc):
    """True se o resto da divisao for zero (nenhum erro detectado)."""
    bits = _bits(bits_with_crc)
    if len(bits) < CRC8_BITS:
        return False
    return not crc8(bits).any()


def crc8_strip(bits_with_crc):
    """Separa (mensagem, ok)."""
    bits = _bits(bits_with_crc)
    return bits[:-CRC8_BITS], crc8_check(bits)


# ----------------------------------------------------------------------
# Hamming (7,4)
# ----------------------------------------------------------------------
def hamming74_encode(bits):
    """Codifica de 4 em 4 bits. Completa com zeros ate multiplo de 4."""
    bits = _bits(bits)
    extra = (-len(bits)) % 4
    if extra:
        bits = np.concatenate([bits, np.zeros(extra, dtype=np.uint8)])
    d = bits.reshape(-1, 4)
    return ((d.astype(int) @ G) % 2).astype(np.uint8).ravel()


def hamming74_syndrome(block):
    """Sindrome (0..7) de um bloco de 7 bits: posicao do erro, 0 = sem erro."""
    s = (H.astype(int) @ _bits(block)) % 2
    return int(s[0] + 2 * s[1] + 4 * s[2])


def hamming74_decode(bits, n_data=None):
    """Decodifica blocos de 7 bits corrigindo 1 erro por bloco.

    Retorna (dados, info):
      dados: bits de dados (4 por bloco), cortados em n_data se dado;
      info:  dict com 'corrigidos' (numero de blocos com sindrome != 0),
             'blocos', 'posicoes' (indice do bit corrigido no array de
             entrada, para cada correcao) e 'sindromes' (uma por bloco).
    Bits que sobram (menos de 7 no fim) sao ignorados.
    """
    bits = _bits(bits)
    nblk = len(bits) // 7
    c = bits[:nblk * 7].reshape(nblk, 7).copy()
    s = (c.astype(int) @ H.T.astype(int)) % 2          # nblk x 3
    synd = s[:, 0] + 2 * s[:, 1] + 4 * s[:, 2]
    fixed = np.flatnonzero(synd)
    c[fixed, synd[fixed] - 1] ^= 1
    data = c[:, DATA_POS].ravel()
    if n_data is not None:
        data = data[:n_data]
    info = dict(blocos=int(nblk), corrigidos=int(len(fixed)),
                posicoes=(fixed * 7 + synd[fixed] - 1).tolist(),
                sindromes=synd.tolist())
    return data, info


# ----------------------------------------------------------------------
# Camada completa (usada pela integracao): CRC + Hamming
# ----------------------------------------------------------------------
def protect(bits):
    """Fluxo -> CRC-8 -> Hamming (7,4). Retorna os bits codificados."""
    return hamming74_encode(crc8_encode(bits))


def coded_length(n_bits):
    """Tamanho em bits depois de protect() para um fluxo de n_bits."""
    n = n_bits + CRC8_BITS
    return 7 * ((n + 3) // 4)


def recover(coded_bits, n_bits):
    """Inverso de protect(): Hamming -> CRC-8.

    n_bits e o tamanho original do fluxo (o TDM informa no cabecalho).
    Retorna (bits, info) com info = {'crc_ok', 'corrigidos', 'posicoes',
    'blocos'}. crc_ok = False indica erro nao corrigido (mais de 1 erro
    em algum bloco).
    """
    data, hinfo = hamming74_decode(coded_bits, n_bits + CRC8_BITS)
    msg, ok = crc8_strip(data)
    return msg, dict(crc_ok=bool(ok), corrigidos=hinfo["corrigidos"],
                     posicoes=hinfo["posicoes"], blocos=hinfo["blocos"])
