"""Simulacao por software do enlace basico (sem placa de som).

Gera em evidencias/simulacao/:
    - um subdiretorio por cenario (figuras + relatorio.json)
    - ber.png / ber.json: BER x Eb/N0 dos dois receptores e a curva teorica
    - resumo.json com todos os cenarios
Tambem decodifica as gravacoes acusticas que vem no modem_acustico.zip
(evidencias/wav_professor/), se a pasta for encontrada.

Exemplo:
    python -m modem_py.simular
    python -m modem_py.simular --rapido
"""

import argparse
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from scipy.special import erfc  # noqa: E402

from .audio import read_wav, write_wav  # noqa: E402
from .channel import ChannelConfig, apply_channel  # noqa: E402
from .config import RxConfig, TxConfig  # noqa: E402
from .evidence import C1, C2, INK2, make_evidence  # noqa: E402
from .framing import bits_to_text, text_to_bits  # noqa: E402
from .receiver import receive_bits  # noqa: E402
from .seq import compare_bits, prbs7  # noqa: E402
from .transmitter import transmit_bits  # noqa: E402

SCENARIOS = [
    # nome, canal, descricao
    ("ideal", ChannelConfig(lead_s=0, tail_s=0, gain=1.0),
     "sem canal: saida do TX direto no RX (como teste.m)"),
    ("realista", ChannelConfig(gain=0.3, phase_rad=1.0, freq_offset_hz=0.5,
                               clock_ppm=100, ebn0_db=12, seed=1),
     "atraso 0.5 s, ganho 0.3, fase 1 rad, desvio 0.5 Hz, relogio 100 ppm, Eb/N0 12 dB"),
    ("fase_180", ChannelConfig(gain=0.5, phase_rad=np.pi, ebn0_db=15, seed=2),
     "portadora com 180 graus: testa a correcao de polaridade pelo SFD"),
    ("ruidoso", ChannelConfig(gain=0.3, phase_rad=2.0, freq_offset_hz=1.0,
                              clock_ppm=200, ebn0_db=6, seed=3),
     "Eb/N0 6 dB, desvio 1 Hz, relogio 200 ppm"),
]


def run_scenario(name, ch, desc, bits, out_base, rx_cfg, tx_cfg):
    y_tx = transmit_bits(bits, tx_cfg)
    y_rx = apply_channel(y_tx, tx_cfg.fa, tx_cfg.rb, ch)
    payload, info = receive_bits(y_rx, rx_cfg)
    cmp_ = compare_bits(bits, payload)
    d = os.path.join(out_base, name)
    os.makedirs(d, exist_ok=True)
    write_wav(os.path.join(d, "sinal_rx_simulado.wav"), y_rx / max(1.0, np.abs(y_rx).max()), tx_cfg.fa)
    rep = make_evidence(d, "simulacao_" + name, tx_cfg, rx_cfg, bits, info, cmp_,
                        tx_audio=y_tx, rx_audio=y_rx,
                        extra=dict(tipo="simulacao", descricao=desc,
                                   canal=ch.__dict__))
    print("  %-10s erros=%d/%d  SFD=%.0f  invertido=%s  SNR_dec=%s dB"
          % (name, cmp_["n_errors"], cmp_["n_sent"], info["peak"], info["inverted"],
             None if rep["sinal"]["snr_decisao_db"] is None
             else round(rep["sinal"]["snr_decisao_db"], 1)))
    return dict(cenario=name, descricao=desc, erros=cmp_["n_errors"],
                bits=cmp_["n_sent"], ber=cmp_["ber"], sfd_ok=info["ok"],
                pico_sfd=info["peak"], invertido=info["inverted"],
                snr_decisao_db=rep["sinal"]["snr_decisao_db"])


def ber_curve(out_base, tx_cfg, ebn0_list, frames, nbits):
    """BER x Eb/N0 com canal AWGN + fase/atraso aleatorios.

    Quadro perdido (SFD nao encontrado) conta todos os bits como errados.
    """
    modes = dict(extras=RxConfig(), professor=RxConfig.professor())
    rng = np.random.default_rng(123)
    res = {m: [] for m in modes}
    lost = {m: [] for m in modes}
    for e in ebn0_list:
        for m, rcfg in modes.items():
            errs = tot = nlost = 0
            for f in range(frames):
                bits = rng.integers(0, 2, nbits).astype(np.uint8)
                ch = ChannelConfig(lead_s=0.2, tail_s=0.2, gain=0.3,
                                   phase_rad=float(rng.uniform(0, 2 * np.pi)),
                                   ebn0_db=e, seed=int(rng.integers(1 << 30)))
                y = apply_channel(transmit_bits(bits, tx_cfg), tx_cfg.fa, tx_cfg.rb, ch)
                payload, info = receive_bits(y, rcfg)
                c = compare_bits(bits, payload)
                if not info["ok"] or len(payload) != nbits:
                    nlost += 1
                    errs += nbits
                else:
                    errs += c["n_errors"]
                tot += nbits
            res[m].append(errs / tot)
            lost[m].append(nlost)
            print("  Eb/N0=%4.1f dB  %-9s BER=%.3e  quadros perdidos=%d/%d"
                  % (e, m, errs / tot, nlost, frames))
    theory = [0.5 * erfc(np.sqrt(10 ** (e / 10))) for e in ebn0_list]

    fig, ax = plt.subplots(figsize=(5.6, 3.8))
    ax.semilogy(ebn0_list, theory, color=INK2, linestyle="--", label="BPSK teorica Q(sqrt(2Eb/N0))")
    floor = 0.5 / (frames * nbits)
    for m, color in (("extras", C1), ("professor", C2)):
        ax.semilogy(ebn0_list, np.maximum(res[m], floor), "o-", color=color,
                    markersize=5, label="receptor %s" % ("com extras" if m == "extras"
                                                         else "receptor_2.m"))
    ax.set_xlabel("Eb/N0 (dB)")
    ax.set_ylabel("BER")
    ax.set_title("BER simulada (%d quadros x %d bits por ponto)" % (frames, nbits))
    ax.legend(loc="lower left")
    fig.tight_layout()
    fig.savefig(os.path.join(out_base, "ber.png"))
    plt.close(fig)
    out = dict(ebn0_db=list(ebn0_list), ber_teorica=theory,
               ber=res, quadros_perdidos=lost, quadros_por_ponto=frames,
               bits_por_quadro=nbits,
               nota="BER zero aparece no grafico no piso 0.5/(quadros*bits)")
    with open(os.path.join(out_base, "ber.json"), "w") as fh:
        json.dump(out, fh, indent=2)
    return out


def professor_wavs(src_dir, out_base, tx_cfg):
    """Decodifica sinal/*.wav do codigo-base (gravacoes acusticas do professor)."""
    out = []
    expected = text_to_bits("OLA")
    for name in sorted(os.listdir(src_dir)):
        if not name.endswith(".wav"):
            continue
        y, _ = read_wav(os.path.join(src_dir, name), tx_cfg.fa)
        for mode, rcfg in (("extras", RxConfig()), ("professor", RxConfig.professor())):
            payload, info = receive_bits(y, rcfg)
            cmp_ = compare_bits(expected, payload)
            text = bits_to_text(payload)
            row = dict(arquivo=name, receptor=mode, sfd_ok=info["ok"],
                       pico_sfd=info["peak"], bytes=info["nbytes"],
                       texto=text if info["ok"] else None,
                       erros_vs_OLA=cmp_["n_errors"] if info["ok"] else None)
            out.append(row)
            print("  %-15s %-9s SFD=%2.0f/32 texto=%r"
                  % (name, mode, info["peak"], text[:12] if info["ok"] else None))
            if mode == "extras" and info["ok"]:
                d = os.path.join(out_base, os.path.splitext(name)[0])
                make_evidence(d, "wav_professor_" + name, tx_cfg, rcfg, expected,
                              info, cmp_, rx_audio=y,
                              extra=dict(tipo="gravacao acustica do codigo-base",
                                         arquivo=name))
    os.makedirs(out_base, exist_ok=True)
    with open(os.path.join(out_base, "resumo.json"), "w") as fh:
        json.dump(out, fh, indent=2)
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description="Simulacao do enlace basico")
    p.add_argument("--saida", default="evidencias")
    p.add_argument("--prbs", type=int, default=64, help="bits do payload dos cenarios")
    p.add_argument("--rapido", action="store_true", help="curva de BER curta")
    p.add_argument("--sem-ber", action="store_true")
    p.add_argument("--wav-professor", default=None,
                   help="pasta sinal/ do modem_acustico (procura em ../modem_acustico/sinal)")
    args = p.parse_args(argv)

    tx_cfg = TxConfig()
    sim_dir = os.path.join(args.saida, "simulacao")
    os.makedirs(sim_dir, exist_ok=True)
    bits = prbs7(args.prbs)

    resumo = {}
    for mode, rcfg in (("extras", RxConfig()), ("professor", RxConfig.professor())):
        print("Cenarios (receptor %s):" % mode)
        resumo[mode] = [run_scenario(n, ch, desc, bits,
                                     os.path.join(sim_dir, mode), rcfg, tx_cfg)
                        for n, ch, desc in SCENARIOS]
    with open(os.path.join(sim_dir, "resumo.json"), "w") as fh:
        json.dump(resumo, fh, indent=2)

    if not args.sem_ber:
        print("Curva de BER:")
        if args.rapido:
            ber_curve(sim_dir, tx_cfg, [0, 4, 8], frames=2, nbits=400)
        else:
            ber_curve(sim_dir, tx_cfg, [0, 2, 4, 6, 8, 10], frames=5, nbits=2000)

    wdir = args.wav_professor
    if wdir is None:
        here = os.path.dirname(os.path.abspath(__file__))
        for cand in (os.path.join(here, "..", "..", "modem_acustico", "sinal"),
                     os.path.join(here, "..", "modem_acustico", "sinal")):
            if os.path.isdir(cand):
                wdir = cand
                break
    if wdir and os.path.isdir(wdir):
        print("Gravacoes do codigo-base (%s):" % os.path.normpath(wdir))
        professor_wavs(wdir, os.path.join(args.saida, "wav_professor"), tx_cfg)


if __name__ == "__main__":
    main()
