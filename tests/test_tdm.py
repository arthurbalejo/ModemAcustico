"""Testes do TDM (modem_py/tdm.py) e do sistema integrado (modem_py/sistema.py).

Rodar com:  .venv/bin/python -m pytest -q tests/test_tdm.py
"""

import json

import numpy as np
import pytest

from modem_py import fec, tdm
from modem_py.channel import ChannelConfig, apply_channel, flip_bits
from modem_py.framing import bits_to_text, text_to_bits
from modem_py.receiver import receive_bits
from modem_py.seq import compare_bits, prbs7
from modem_py.transmitter import transmit_bits


def _streams():
    return text_to_bits("OLA"), prbs7(40, seed=0x35)


# ----------------------------------------------------------------------
# Cabecalho e agenda de slots
# ----------------------------------------------------------------------
def test_cabecalho_ida_e_volta():
    h = tdm.encode_header(24, 1000, 7, True)
    assert len(h) == tdm.HEADER_BITS == 70
    d = tdm.decode_header(h)
    assert (d["n_a"], d["n_b"], d["slot"], d["fec"], d["ok"]) == (24, 1000, 7, True, True)


@pytest.mark.parametrize("pos", range(0, 70, 7))
def test_cabecalho_corrige_um_erro_por_bloco(pos):
    h = flip_bits(tdm.encode_header(24, 40, 3, False), [pos + 3])
    d = tdm.decode_header(h)
    assert d["ok"] and d["corrigidos"] == 1
    assert (d["n_a"], d["n_b"], d["slot"], d["fec"]) == (24, 40, 3, False)


def test_cabecalho_com_dois_erros_no_bloco_e_acusado():
    h = flip_bits(tdm.encode_header(24, 40, 7, True), [0, 1])
    assert not tdm.decode_header(h)["ok"]


def test_agenda_rodizio_e_fluxo_que_acaba():
    # A com 10 bits, B com 3, slot 4: A4 B3 A4 A2
    assert tdm.slot_schedule([10, 3], 4) == [(0, 0, 4), (1, 0, 3), (0, 4, 4), (0, 8, 2)]
    assert tdm.slot_map([10, 3], 4).tolist() == [0] * 4 + [1] * 3 + [0] * 6


def test_intercalacao_bit_a_bit():
    a = np.array([1, 1, 1, 1], np.uint8)
    b = np.array([0, 0, 0, 0], np.uint8)
    assert tdm.interleave([a, b], 1).tolist() == [1, 0, 1, 0, 1, 0, 1, 0]


@pytest.mark.parametrize("slot", [1, 4, 7, 16])
@pytest.mark.parametrize("na,nb", [(24, 40), (0, 13), (101, 0), (1, 1)])
def test_interleave_deinterleave(slot, na, nb):
    a, b = prbs7(na, 0x11), prbs7(nb, 0x5A)
    x = tdm.interleave([a, b], slot)
    a2, b2 = tdm.deinterleave(x, [na, nb], slot)
    assert a2.tolist() == a.tolist() and b2.tolist() == b.tolist()


# ----------------------------------------------------------------------
# MUX / DEMUX sem modulacao
# ----------------------------------------------------------------------
@pytest.mark.parametrize("use_fec", [True, False])
@pytest.mark.parametrize("slot", [1, 7])
def test_mux_demux_direto(use_fec, slot):
    a, b = _streams()
    bits = tdm.mux(a, b, slot, use_fec)
    assert len(bits) == tdm.mux_length(len(a), len(b), use_fec)
    # o enlace devolve o payload completado ate multiplo de 8
    padded = np.concatenate([bits, np.zeros((-len(bits)) % 8, np.uint8)])
    a2, b2, info = tdm.demux(padded)
    assert info["cabecalho_ok"] and info["completo"]
    assert a2.tolist() == a.tolist() and b2.tolist() == b.tolist()


def test_um_erro_por_palavra_e_corrigido_nos_dois_fluxos():
    a, b = _streams()
    bits = tdm.mux(a, b, 7, True)
    # slot = 7: cada slot e uma palavra Hamming; 1 erro em cada slot
    n_slots = (len(bits) - tdm.HEADER_BITS) // 7
    pos = [tdm.HEADER_BITS + 7 * k + (k % 7) for k in range(n_slots)]
    a2, b2, info = tdm.demux(flip_bits(bits, pos))
    assert a2.tolist() == a.tolist() and b2.tolist() == b.tolist()
    assert all(f["crc_ok"] for f in info["fluxos"])
    assert sum(f["corrigidos"] for f in info["fluxos"]) == n_slots


def test_rajada_com_slot_1_e_corrigida():
    # rajada de 2 bits seguidos: com slot 1 cai em fluxos diferentes
    a, b = _streams()
    p = tdm.HEADER_BITS + 21           # inicio de um slot
    a7, b7, i7 = tdm.demux(flip_bits(tdm.mux(a, b, 7), [p, p + 1]))
    a1, b1, i1 = tdm.demux(flip_bits(tdm.mux(a, b, 1), [p, p + 1]))
    assert not all(f["crc_ok"] for f in i7["fluxos"])       # 2 erros na mesma palavra
    assert all(f["crc_ok"] for f in i1["fluxos"])
    assert a1.tolist() == a.tolist() and b1.tolist() == b.tolist()


def test_limite_do_quadro():
    with pytest.raises(ValueError):
        tdm.mux(prbs7(600), prbs7(600))
    big = tdm.MAX_PAYLOAD_BITS - tdm.HEADER_BITS
    assert len(tdm.mux(prbs7(big - 1), prbs7(1), use_fec=False)) <= tdm.MAX_PAYLOAD_BITS


def test_payload_cortado_e_sinalizado():
    a, b = _streams()
    bits = tdm.mux(a, b)
    _, _, info = tdm.demux(bits[:-20])
    assert not info["completo"]


# ----------------------------------------------------------------------
# Com modulacao (T14 / T15 do plano de testes, em simulacao)
# ----------------------------------------------------------------------
def test_tdm_pelo_enlace_ideal():
    a, b = _streams()
    payload, rinfo = receive_bits(transmit_bits(tdm.mux(a, b)))
    a2, b2, info = tdm.demux(payload)
    assert rinfo["ok"] and info["cabecalho_ok"]
    assert bits_to_text(a2) == "OLA" and compare_bits(b, b2)["equal"]


def test_tdm_pelo_canal_realista():
    a, b = text_to_bits("FLUXO A"), prbs7(64, seed=0x35)
    ch = ChannelConfig(gain=0.3, phase_rad=1.0, freq_offset_hz=0.5,
                       clock_ppm=100, ebn0_db=12, seed=1)
    y = apply_channel(transmit_bits(tdm.mux(a, b, 1)), 8000, 100, ch)
    a2, b2, info = tdm.demux(receive_bits(y)[0])
    assert all(f["crc_ok"] for f in info["fluxos"])
    assert compare_bits(a, a2)["equal"] and compare_bits(b, b2)["equal"]


def test_cli_sistema_simular(tmp_path):
    from modem_py import sistema
    assert sistema.main(["simular", "--ideal", "--a-texto", "OLA", "--b-prbs", "24",
                         "--erros", "3", "--slot", "1",
                         "--evidencias", str(tmp_path)]) == 0
    rep = list(tmp_path.glob("*/tdm.json"))
    assert len(rep) == 1
    data = json.loads(rep[0].read_text())
    assert data["fluxos"][0]["texto"] == "OLA"


def test_cli_sistema_tx_rx_por_wav(tmp_path):
    from modem_py import sistema
    wav = str(tmp_path / "tdm.wav")
    assert sistema.main(["tx", "--a-texto", "OLA", "--b-prbs", "40", "--wav", wav]) == 0
    assert sistema.main(["rx", "--wav", wav, "--esperado-a-texto", "OLA",
                         "--esperado-b-prbs", "40"]) == 0


def test_tamanho_do_cabecalho_bate_com_fec():
    assert tdm.HEADER_BITS == fec.coded_length(tdm.HEADER_INFO_BITS)
