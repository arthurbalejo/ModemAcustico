"""Evidencias para o relatorio: figuras (PNG) e relatorio JSON."""

import json
import os
import platform
import time
from dataclasses import asdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from scipy.signal import welch  # noqa: E402

from .framing import SFD  # noqa: E402
from .seq import bits_to_str  # noqa: E402

# Paleta (azul, laranja, verde-agua) + vermelho so para marcar erros.
C1, C2, C3, CERR = "#2a78d6", "#eb6834", "#1baf7a", "#e34948"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"

plt.rcParams.update({
    "figure.dpi": 110, "savefig.dpi": 150, "font.size": 9,
    "axes.edgecolor": INK2, "axes.labelcolor": INK, "axes.titlesize": 10,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False,
    "xtick.color": INK2, "ytick.color": INK2, "lines.linewidth": 1.2,
    "legend.frameon": False,
})


def _save(fig, out_dir, name):
    path = os.path.join(out_dir, name)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_spectrum(out_dir, fa, fp, rb, rolloff, tx=None, rx=None):
    fig, ax = plt.subplots(figsize=(6.4, 3.2))
    for y, label, color in ((tx, "transmitido", C1), (rx, "recebido", C2)):
        if y is None or len(y) < 256:
            continue
        f, p = welch(y, fa, nperseg=1024)
        p_db = 10 * np.log10(p / p.max() + 1e-12)
        ax.plot(f, p_db, color=color, label=label)
    bw = (1 + rolloff) * rb / 2
    ax.axvspan(fp - bw, fp + bw, color=C3, alpha=0.15,
               label="Fp +- (1+r)Rb/2 = %.0f-%.0f Hz" % (fp - bw, fp + bw))
    ax.set_xlim(0, fa / 2)
    ax.set_ylim(-80, 3)
    ax.set_xlabel("frequencia (Hz)")
    ax.set_ylabel("DEP normalizada (dB)")
    ax.set_title("Espectro do sinal BPSK (Welch)")
    ax.legend(loc="upper right")
    return _save(fig, out_dir, "espectro.png")


def frame_slice(info, margin=40):
    """Indices (em simbolos decididos) do quadro: PRE + SFD + LEN + payload + PRE."""
    k = info["sfd_index"]
    if k < 0:
        return slice(10, None)
    end = k + len(SFD) + 8 + 8 * info["nbytes"] + margin
    return slice(max(0, k - margin + 10), min(end, len(info["raw_bits"])))


def plot_eye(out_dir, diag, fa, rb, sl):
    st = int(np.ceil(fa / rb))
    i_br = diag["i"]
    si = diag["sample_index"][sl]
    ref = np.median(np.abs(diag["samples"][sl])) or 1.0
    fig, ax = plt.subplots(figsize=(5.2, 3.4))
    tt = np.arange(-st, st + 1) / st
    count = 0
    for s in si:
        if s - st < 0 or s + st >= len(i_br):
            continue
        ax.plot(tt, i_br[s - st:s + st + 1] / ref, color=C1, alpha=0.25,
                linewidth=0.8)
        count += 1
    ax.axvline(0, color=INK2, linewidth=0.8, linestyle="--")
    ax.set_xlabel("tempo (periodos de simbolo, 0 = instante de amostragem)")
    ax.set_ylabel("ramo I normalizado")
    ax.set_title("Diagrama de olho (%d tracos)" % count)
    return _save(fig, out_dir, "olho.png")


def plot_constellation(out_dir, diag, sl):
    s_i = diag["samples"][sl]
    s_q = diag["samples_q"][sl]
    ref = np.median(np.abs(s_i)) or 1.0
    fig, ax = plt.subplots(figsize=(4.0, 4.0))
    m = s_i > 0
    ax.scatter(s_i[m] / ref, s_q[m] / ref, s=10, color=C1, label="bit 1")
    ax.scatter(s_i[~m] / ref, s_q[~m] / ref, s=10, color=C2, label="bit 0")
    lim = max(1.6, float(np.max(np.abs(np.r_[s_i, s_q] / ref))) * 1.1)
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.axhline(0, color=INK2, linewidth=0.6)
    ax.axvline(0, color=INK2, linewidth=0.6)
    ax.set_aspect("equal")
    ax.set_xlabel("I (em fase)")
    ax.set_ylabel("Q (quadratura)")
    ax.set_title("Constelacao nos instantes de decisao")
    ax.legend(loc="upper left")
    return _save(fig, out_dir, "constelacao.png")


def plot_sfd_corr(out_dir, info, threshold):
    corr = info["corr"]
    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    ax.plot(np.arange(len(corr)), corr, color=C1, label="correlacao")
    lim = threshold * len(SFD)
    ax.axhline(lim, color=INK2, linestyle="--", linewidth=0.8,
               label="limiar +-%.1f" % lim)
    ax.axhline(-lim, color=INK2, linestyle="--", linewidth=0.8)
    if info["sfd_index"] >= 0:
        ax.plot([info["sfd_index"]], [info["peak"]], "o", color=C2,
                markersize=6, label="pico = %.0f no bit %d"
                % (info["peak"], info["sfd_index"]))
    ax.set_ylim(-len(SFD) - 2, len(SFD) + 2)
    ax.set_xlabel("posicao de inicio do SFD (bits decididos)")
    ax.set_ylabel("correlacao")
    ax.set_title("Sincronizacao de quadro: correlacao com o SFD (32 bits)")
    ax.legend(loc="lower right")
    return _save(fig, out_dir, "correlacao_sfd.png")


def plot_bits(out_dir, sent, received, cmp_):
    n = len(sent)
    fig, axes = plt.subplots(2, 1, figsize=(7.0, 3.2), sharex=True)
    x = np.arange(n)
    rec = np.zeros(n)
    m = min(n, len(received))
    rec[:m] = received[:m]
    axes[0].step(x, sent, where="post", color=C1)
    axes[0].set_ylabel("enviado")
    axes[1].step(x, rec, where="post", color=C2)
    axes[1].set_ylabel("recebido")
    errs = cmp_["error_positions"]
    for ax in axes:
        ax.set_ylim(-0.3, 1.3)
        ax.set_yticks([0, 1])
        for e in errs:
            ax.axvspan(e, e + 1, color=CERR, alpha=0.35, linewidth=0)
    axes[1].set_xlabel("indice do bit de payload")
    axes[0].set_title("Bits enviados x recebidos: %d erros em %d bits (BER = %.4g)"
                      % (cmp_["n_errors"], cmp_["n_sent"], cmp_["ber"]))
    return _save(fig, out_dir, "bits_enviados_recebidos.png")


def plot_sync(out_dir, diag, fa):
    """Fase estimada pelo Costas e ramo I com os instantes de amostragem."""
    t = np.arange(len(diag["i"])) / fa
    fig, axes = plt.subplots(2, 1, figsize=(7.0, 4.0), sharex=True)
    axes[0].plot(t, diag["theta"], color=C1)
    axes[0].set_ylabel("theta (rad)")
    axes[0].set_title("Laco de Costas (fase) e sincronizacao cedo-tarde")
    axes[1].plot(t, diag["i"], color=C1, linewidth=0.6)
    si = diag["sample_index"]
    axes[1].plot(si / fa, diag["i"][si], ".", color=C2, markersize=3,
                 label="instantes de decisao")
    axes[1].set_ylabel("ramo I")
    axes[1].set_xlabel("tempo (s)")
    axes[1].legend(loc="upper right")
    return _save(fig, out_dir, "sincronizacao.png")


def decision_snr_db(samples, sl=slice(10, None)):
    """SNR estimada na decisao, so no trecho do quadro: media(|s|)^2 / var(|s|), em dB."""
    s = np.abs(np.asarray(samples)[sl])
    if len(s) < 3 or np.var(s) == 0:
        return None
    return float(10 * np.log10(np.mean(s) ** 2 / np.var(s)))


def make_evidence(out_dir, scenario, tx_cfg, rx_cfg, sent_bits, info, cmp_,
                  tx_audio=None, rx_audio=None, extra=None):
    """Gera todas as figuras e o relatorio.json em out_dir."""
    os.makedirs(out_dir, exist_ok=True)
    diag = info["diag"]
    sl = frame_slice(info)
    figs = [
        plot_spectrum(out_dir, rx_cfg.fa, rx_cfg.fp, rx_cfg.rb, tx_cfg.rolloff,
                      tx_audio, rx_audio),
        plot_eye(out_dir, diag, rx_cfg.fa, rx_cfg.rb, sl),
        plot_constellation(out_dir, diag, sl),
        plot_sfd_corr(out_dir, info, rx_cfg.sfd_threshold),
        plot_bits(out_dir, sent_bits, info["payload"], cmp_),
        plot_sync(out_dir, diag, rx_cfg.fa),
    ]
    rx_level = float(np.max(np.abs(rx_audio))) if rx_audio is not None and len(rx_audio) else None
    report = dict(
        cenario=scenario,
        data=time.strftime("%Y-%m-%d %H:%M:%S"),
        maquina=platform.node(),
        tx_config=asdict(tx_cfg),
        rx_config=asdict(rx_cfg),
        quadro=dict(
            sfd_encontrado=info["ok"], pico_correlacao=info["peak"],
            posicao_sfd_bit=info["sfd_index"], polaridade_invertida=info["inverted"],
            bytes_cabecalho=info["nbytes"], payload_completo=info["complete"],
            bits_decididos=int(len(info["raw_bits"])),
        ),
        comparacao=dict(
            bits_enviados=bits_to_str(sent_bits),
            bits_recebidos=bits_to_str(info["payload"]),
            **cmp_,
        ),
        sinal=dict(
            amostras_tx=int(len(tx_audio)) if tx_audio is not None else None,
            duracao_tx_s=float(len(tx_audio) / tx_cfg.fa) if tx_audio is not None else None,
            amostras_rx=int(len(rx_audio)) if rx_audio is not None else None,
            pico_rx=rx_level,
            snr_decisao_db=decision_snr_db(diag["samples"], sl),
        ),
        figuras=[os.path.basename(f) for f in figs],
    )
    if extra:
        report.update(extra)
    with open(os.path.join(out_dir, "relatorio.json"), "w") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=True)
    return report
