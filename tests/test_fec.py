"""Testes T11 a T14: CRC-8 e Hamming (7,4) (simulacao por software).

Erros introduzidos de forma controlada com channel.flip_bits, direto nos
bits entre as camadas (sem passar pela modulacao).

Rodar com:  .venv/bin/python -m pytest -q tests/test_fec.py
"""

import itertools

import numpy as np
import pytest

from modem_py.channel import flip_bits
from modem_py.fec import (G, H, coded_length, crc8, crc8_check, crc8_encode,
                          hamming74_decode, hamming74_encode, hamming74_syndrome,
                          protect, recover)
from modem_py.framing import bytes_to_bits, text_to_bits
from modem_py.seq import prbs7


# ----------------------------------------------------------------------
# Verificacoes basicas
# ----------------------------------------------------------------------
def _crc_bytes_msb(data):
    """CRC-8/SMBUS de referencia (bytes, MSB primeiro, tabela classica)."""
    reg = 0
    for byte in data:
        reg ^= byte
        for _ in range(8):
            reg = ((reg << 1) ^ 0x07) & 0xFF if reg & 0x80 else (reg << 1) & 0xFF
    return reg


def test_crc8_valor_de_referencia():
    # Vetor de verificacao do CRC-8/SMBUS: "123456789" -> 0xF4
    msg = b"123456789"
    bits_msb = np.unpackbits(np.frombuffer(msg, dtype=np.uint8))
    crc = crc8(bits_msb)
    assert int("".join(map(str, crc)), 2) == 0xF4 == _crc_bytes_msb(msg)


def test_crc8_resto_zero():
    for n in (1, 7, 8, 13, 64, 200):
        assert crc8_check(crc8_encode(prbs7(n)))


def test_hamming_matrizes():
    assert not ((G.astype(int) @ H.T.astype(int)) % 2).any()   # G H^T = 0
    for j in range(7):                                         # coluna j = j+1
        e = np.zeros(7, np.uint8)
        e[j] = 1
        assert hamming74_syndrome(e) == j + 1


def test_hamming_sem_erro_ida_e_volta():
    bits = text_to_bits("UFSM")
    code = hamming74_encode(bits)
    assert len(code) == 7 * len(bits) // 4
    out, info = hamming74_decode(code)
    assert out.tolist() == bits.tolist() and info["corrigidos"] == 0


def test_hamming_completa_ate_multiplo_de_4():
    bits = prbs7(10)
    out, _ = hamming74_decode(hamming74_encode(bits), n_data=10)
    assert out.tolist() == bits.tolist()


# ----------------------------------------------------------------------
# T11: CRC-8 detecta erros
# ----------------------------------------------------------------------
@pytest.mark.parametrize("nerr", [1, 2, 3])
def test_T11_crc_detecta_1_2_3_erros(nerr):
    # 8 bytes de dados (64 bits) + CRC: dentro da distancia 4 do CRC-8 (<= 119 bits)
    rng = np.random.default_rng(11 + nerr)
    for _ in range(1000):
        msg = rng.integers(0, 2, 64).astype(np.uint8)
        tx = crc8_encode(msg)
        pos = rng.choice(len(tx), nerr, replace=False)
        assert not crc8_check(flip_bits(tx, pos))


def test_T11_crc_sem_erro_sempre_aceito():
    rng = np.random.default_rng(110)
    for _ in range(1000):
        assert crc8_check(crc8_encode(rng.integers(0, 2, 64).astype(np.uint8)))


def test_T11_crc_todos_os_pares_ate_119_bits():
    # Varredura exaustiva: todos os pares de erros em 119 bits de dados + CRC.
    tx = crc8_encode(prbs7(119))
    for i, j in itertools.combinations(range(len(tx)), 2):
        assert not crc8_check(flip_bits(tx, [i, j]))


def test_T11_crc_detecta_numero_impar_de_erros():
    rng = np.random.default_rng(111)
    tx = crc8_encode(rng.integers(0, 2, 800).astype(np.uint8))   # bem acima de 119
    for nerr in (1, 3, 5, 7, 9):
        for _ in range(200):
            pos = rng.choice(len(tx), nerr, replace=False)
            assert not crc8_check(flip_bits(tx, pos))


def test_T11_crc_detecta_rajadas_ate_8_bits():
    tx = crc8_encode(prbs7(200))
    for length in range(1, 9):
        for start in range(len(tx) - length + 1):
            # rajada: primeiro e ultimo bit trocados, os do meio todos trocados
            assert not crc8_check(flip_bits(tx, range(start, start + length)))


# ----------------------------------------------------------------------
# T12: Hamming corrige 1 erro (7 posicoes x 16 palavras = 112 casos)
# ----------------------------------------------------------------------
def test_T12_hamming_corrige_um_erro_em_cada_posicao():
    casos = 0
    for d in range(16):
        data = np.array([(d >> i) & 1 for i in range(4)], dtype=np.uint8)
        code = hamming74_encode(data)
        for pos in range(7):
            rx = flip_bits(code, [pos])
            assert hamming74_syndrome(rx) == pos + 1        # sindrome aponta o bit
            out, info = hamming74_decode(rx)
            assert out.tolist() == data.tolist()
            assert info["corrigidos"] == 1 and info["posicoes"] == [pos]
            casos += 1
    assert casos == 112


def test_T12_um_erro_por_bloco_em_mensagem_longa():
    # "UFSM" -> 8 blocos; um erro em cada bloco, todos corrigidos
    bits = text_to_bits("UFSM")
    code = hamming74_encode(bits)
    rng = np.random.default_rng(12)
    pos = [7 * k + int(rng.integers(7)) for k in range(len(code) // 7)]
    out, info = hamming74_decode(flip_bits(code, pos))
    assert out.tolist() == bits.tolist()
    assert info["corrigidos"] == len(pos) and info["posicoes"] == pos


# ----------------------------------------------------------------------
# T13: limite do Hamming (2 erros no mesmo bloco) e CRC acusando
# ----------------------------------------------------------------------
def test_T13_dois_erros_no_bloco_corrige_errado_e_crc_acusa():
    msg = bytes_to_bits([0xA5])                 # 1 byte de dados
    coded = protect(msg)                        # 16 bits -> 4 blocos de 7
    assert len(coded) == coded_length(8) == 28
    miscorrigidos = crc_falhou = 0
    for blk in range(len(coded) // 7):
        for i, j in itertools.combinations(range(7), 2):        # 21 pares
            rx = flip_bits(coded, [7 * blk + i, 7 * blk + j])
            # Hamming sozinho: o bloco sai diferente do original
            data, _ = hamming74_decode(rx)
            ref, _ = hamming74_decode(coded)
            if data.tolist() != ref.tolist():
                miscorrigidos += 1
            out, info = recover(rx, 8)
            if not info["crc_ok"]:
                crc_falhou += 1
            assert info["corrigidos"] >= 1              # o decodificador "corrigiu"
    assert miscorrigidos == 4 * 21
    assert crc_falhou == 4 * 21


# ----------------------------------------------------------------------
# T14: CRC + Hamming com erros aleatorios
# ----------------------------------------------------------------------
def test_T14_crc_hamming_erros_aleatorios():
    rng = np.random.default_rng(14)
    msg = rng.integers(0, 2, 32 * 8).astype(np.uint8)       # fluxo de 32 bytes
    coded = protect(msg)
    for p in (1e-3, 1e-2, 5e-2, 1e-1):
        err_in = err_out = erradas = nao_detectadas = 0
        for _ in range(200):
            mask = rng.random(len(coded)) < p
            rx = coded ^ mask.astype(np.uint8)
            out, info = recover(rx, len(msg))
            nerr = int((out != msg).sum())
            err_in += int(mask.sum())
            err_out += nerr
            if nerr:
                erradas += 1
                nao_detectadas += int(info["crc_ok"])
        ber_in = err_in / (200 * len(coded))
        ber_out = err_out / (200 * len(msg))
        assert ber_out < ber_in
        # CRC-8 deixa passar ~1/256 das mensagens erradas com muitos erros
        assert nao_detectadas <= max(1, 0.02 * erradas)


# ----------------------------------------------------------------------
# Camada completa (interface para o TDM e para o sistema integrado)
# ----------------------------------------------------------------------
def test_protect_recover_texto():
    msg = text_to_bits("UFSM")
    coded = protect(msg)
    assert len(coded) == coded_length(len(msg)) == 7 * (32 + 8) // 4
    out, info = recover(flip_bits(coded, [3, 20, 50]), len(msg))   # 3 blocos, 1 erro cada
    assert out.tolist() == msg.tolist()
    assert info["crc_ok"] and info["corrigidos"] == 3
