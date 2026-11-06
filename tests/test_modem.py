"""Testes do enlace basico (simulacao por software).

Rodar com:  .venv/bin/python -m pytest -q
"""

import os
import pathlib

import numpy as np
import pytest

from modem_py.channel import ChannelConfig, apply_channel, flip_bits
from modem_py.config import RxConfig, TxConfig
from modem_py.framing import (PRE, SFD, bits_to_bytes, bits_to_text, build_frame,
                              bytes_to_bits, parse_frame, text_to_bits)
from modem_py.rcos import rcosine
from modem_py.receiver import receive_bits, receive_text
from modem_py.seq import compare_bits, prbs7
from modem_py.transmitter import transmit_bits, transmit_text

ROOT = pathlib.Path(__file__).resolve().parents[1]
WAV_DIR = ROOT.parent / "modem_acustico" / "sinal"


def test_rcosine_igual_ao_original():
    num = rcosine(100, 8000, 0.5, 3)
    assert len(num) == 2 * 3 * 80 + 1
    assert np.isclose(num.sum(), 1.0)
    assert np.allclose(num, num[::-1])
    # cruza zero nos multiplos do periodo de simbolo (filtro de Nyquist)
    assert np.allclose(num[240 + 80::80], 0, atol=1e-12)


def test_bits_lsb_primeiro_como_de2bi():
    # 'O' = 0x4F = 0100 1111 -> LSB primeiro: 1 1 1 1 0 0 1 0
    assert bytes_to_bits([0x4F]).tolist() == [1, 1, 1, 1, 0, 0, 1, 0]
    assert bits_to_text(text_to_bits("OLA")) == "OLA"
    assert bits_to_bytes(bytes_to_bits([0, 1, 255])).tolist() == [0, 1, 255]


def test_quadro():
    payload = text_to_bits("OLA")
    f = build_frame(payload)
    assert len(PRE) == 40 and len(SFD) == 32
    assert len(f) == 40 + 32 + 8 + 24 + 40
    assert f[:40].tolist() == PRE.tolist()
    assert f[40:72].tolist() == SFD.tolist()
    assert bits_to_bytes(f[72:80])[0] == 3


def test_payload_nao_multiplo_de_8_e_completado():
    bits = prbs7(13)
    out, info = receive_bits(transmit_bits(bits))
    assert info["nbytes"] == 2
    assert out[:13].tolist() == bits.tolist()
    assert out[13:].tolist() == [0, 0, 0]


@pytest.mark.parametrize("cfg", [RxConfig(), RxConfig.professor()],
                         ids=["extras", "professor"])
def test_loopback_ideal_ola(cfg):
    # como o teste.m: saida do transmissor direto no receptor
    text, info = receive_text(transmit_text("OLA"), cfg)
    assert info["ok"] and text == "OLA"


def test_canal_realista_sem_erros():
    bits = prbs7(64)
    ch = ChannelConfig(gain=0.3, phase_rad=1.0, freq_offset_hz=0.5,
                       clock_ppm=100, ebn0_db=12, seed=1)
    y = apply_channel(transmit_bits(bits), 8000, 100, ch)
    out, info = receive_bits(y)
    assert info["ok"]
    assert compare_bits(bits, out)["equal"]


def test_fase_180_corrigida_pelo_sfd():
    bits = prbs7(64)
    ch = ChannelConfig(gain=0.5, phase_rad=np.pi, ebn0_db=15, seed=2)
    out, info = receive_bits(apply_channel(transmit_bits(bits), 8000, 100, ch))
    assert info["inverted"]
    assert compare_bits(bits, out)["equal"]


def test_limiar_do_sfd():
    f = build_frame(prbs7(16))
    one = flip_bits(f, [41])               # 1 erro no SFD: pico 30 >= 28.8
    assert parse_frame(one)["ok"]
    three = flip_bits(f, [41, 50, 60])     # 3 erros: pico 26 < 28.8
    assert not parse_frame(three)["ok"]


def test_sem_sinal_nao_decodifica():
    rng = np.random.default_rng(0)
    _, info = receive_bits(rng.normal(0, 0.1, 16000))
    assert not info["ok"]


def test_amplitude_da_saida():
    y = transmit_bits(prbs7(32), TxConfig(amplitude=0.5))
    assert np.isclose(np.max(np.abs(y)), 0.5)


@pytest.mark.skipif(not WAV_DIR.is_dir(), reason="modem_acustico/sinal nao encontrado")
@pytest.mark.parametrize("name", ["sinal_rx.wav", "sinal_rx2.wav"])
@pytest.mark.parametrize("cfg", [RxConfig(), RxConfig.professor()],
                         ids=["extras", "professor"])
def test_gravacoes_do_codigo_base(name, cfg):
    from modem_py.audio import read_wav
    y, _ = read_wav(str(WAV_DIR / name), 8000)
    text, info = receive_text(y, cfg)
    assert info["ok"] and text == "OLA"


def test_cli_tx_rx_por_wav(tmp_path):
    from modem_py import rx, tx
    wav = str(tmp_path / "s.wav")
    tx.main(["--prbs", "40", "--wav", wav])
    assert rx.main(["--wav", wav, "--esperado-prbs", "40"]) == 0


def test_codigo_somente_ascii():
    for p in list((ROOT / "modem_py").glob("*.py")) + list((ROOT / "tests").glob("*.py")):
        data = p.read_bytes()
        assert all(b < 128 for b in data), "caractere nao ASCII em %s" % os.path.relpath(p, ROOT)
