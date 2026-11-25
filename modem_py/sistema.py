"""Sistema completo: dois fluxos -> CRC-8 -> Hamming -> TDM -> enlace BPSK.

    TX: A, B -> CRC-8 -> Hamming (7,4) -> MUX -> transmit_bits
    RX: receive_bits -> DEMUX -> Hamming (7,4) -> CRC-8 -> A', B'

Modos:
    simular   tudo em software, com o canal de channel.py (e erros injetados)
    tx        gera o sinal (WAV e/ou toca na placa de som)
    rx        decodifica de um WAV ou do microfone
    acustico  toca e grava na mesma maquina

Exemplos:
    python -m modem_py.sistema simular --a-texto OLA --b-prbs 40
    python -m modem_py.sistema simular --erros 6 --slot 1 --evidencias evidencias
    python -m modem_py.sistema tx --a-texto OLA --b-prbs 40 --wav tdm.wav
    python -m modem_py.sistema rx --wav tdm.wav --esperado-a-texto OLA --esperado-b-prbs 40
    python -m modem_py.sistema acustico --a-texto OLA --b-prbs 40
    python -m modem_py.sistema rx --gravar 10 --nivel 0.02 --esperado-a-texto OLA --esperado-b-prbs 40 --evidencias evidencias --cenario sistema_celular_pc
    python -m modem_py.sistema tx --a-texto OLA --b-texto MUNDO --wav tdm.wav
    python -m modem_py.sistema rx --gravar 10 --nivel 0.02 --esperado-a-texto OLA --esperado-b-texto MUNDO --evidencias evidencias --cenario sistema_celular_pc_2_fluxos
"""

import argparse
import json
import os

import numpy as np

from . import _args, tdm
from .channel import ChannelConfig, apply_channel, flip_bits
from .framing import SFD, bits_to_bytes, bits_to_text, text_to_bits
from .receiver import receive_bits
from .seq import bits_to_str, compare_bits, prbs7
from .transmitter import transmit_bits

NOMES = ("A", "B")


# ----------------------------------------------------------------------
# Argumentos
# ----------------------------------------------------------------------
def _add_streams(p, prefix=""):
    for s in ("a-", "b-"):
        _args.add_payload_args(p, prefix=prefix + s)


def _streams_from_args(args, prefix=""):
    """Fluxos pedidos na linha de comando. Padrao: A = texto, B = PRBS."""
    a, da = _args.payload_from_args(args, prefix=prefix + "a-")
    b, db = _args.payload_from_args(args, prefix=prefix + "b-")
    if not prefix:
        if a is None:
            a, da = text_to_bits("MODEM"), "texto: 'MODEM'"
        if b is None:
            b, db = prbs7(40, seed=0x35), "PRBS-7 (semente 0x35), 40 bits"
    return [a, b], [da, db]


def _add_tdm_args(p):
    p.add_argument("--slot", type=int, default=tdm.SLOT_BITS,
                   help="bits por slot TDM, 1 a 16 (padrao %d)" % tdm.SLOT_BITS)
    p.add_argument("--sem-fec", action="store_true",
                   help="multiplexa os fluxos sem CRC-8/Hamming")


# ----------------------------------------------------------------------
# Relatorio
# ----------------------------------------------------------------------
def _short(text, n=80):
    return text if len(text) <= n else text[:n] + "... (%d no total)" % len(text)


def print_link(rx_info, extra=""):
    """Linha do enlace e aviso claro quando nao ha quadro."""
    copias = rx_info.get("copias")
    if copias:
        extra = ", %d copia(s) do quadro na gravacao%s" % (copias, extra)
    print("Enlace: SFD %s (pico %.0f/32), %d bytes%s"
          % ("ok" if rx_info["ok"] else "NAO encontrado", abs(rx_info["peak"]),
             rx_info["nbytes"], extra))
    if not rx_info["ok"]:
        print("*** Nenhum quadro valido no audio recebido: o receptor so decidiu bits")
        print("*** em cima de ruido. Confira microfone, volume e distancia.")


def report_streams(streams, descs, rx_streams, info, verbose=True, rx_info=None):
    """Compara cada fluxo e imprime o resumo. Retorna lista de dicts.

    Se o CRC do cabecalho TDM falhar, os tamanhos lidos nao sao confiaveis:
    os fluxos nao sao separados e contam como nao recebidos.
    """
    h = info["cabecalho"]
    link_ok = rx_info is None or rx_info["ok"]
    if verbose:
        print("Cabecalho TDM: n_A=%d, n_B=%d, slot=%d, FEC=%s, CRC %s, %d bloco(s) corrigido(s)"
              % (h["n_a"], h["n_b"], h["slot"], "sim" if h["fec"] else "nao",
                 "ok" if h["ok"] else "FALHOU", h["corrigidos"]))
        if not h["ok"]:
            print("*** Cabecalho TDM invalido: os tamanhos acima sao lixo e os fluxos")
            print("*** nao foram separados (contam como nao recebidos).")
        elif not info["completo"]:
            print("Payload menor que o anunciado no cabecalho (quadro cortado?)")
    if not h["ok"]:
        rx_streams = [np.zeros(0, np.uint8), np.zeros(0, np.uint8)]
    out = []
    for k, (rx, fi) in enumerate(zip(rx_streams, info["fluxos"])):
        if not h["ok"]:
            fi = dict(crc_ok=False, corrigidos=0, posicoes=[], blocos=0) if fi else {}
        r = dict(fluxo=NOMES[k], bits=bits_to_str(rx), texto=bits_to_text(rx),
                 quadro_ok=bool(link_ok), cabecalho_ok=bool(h["ok"]), **fi)
        if streams is not None and streams[k] is not None:
            cmp_ = compare_bits(streams[k], rx)
            r.update(esperado=descs[k], comparacao=cmp_)
        out.append(r)
        if verbose:
            if not h["ok"]:
                line = "Fluxo %s: NAO recebido" % NOMES[k]
                if "comparacao" in r:
                    line += " (%d bits esperados)" % r["comparacao"]["n_sent"]
                print(line)
                continue
            line = "Fluxo %s: %d bits" % (NOMES[k], len(rx))
            if fi:
                line += ", CRC %s, %d correcao(oes)" % ("ok" if fi["crc_ok"] else "FALHOU",
                                                        fi["corrigidos"])
            if "comparacao" in r:
                c = r["comparacao"]
                line += ", %d erros (BER = %.4g)" % (c["n_errors"], c["ber"])
            print(line)
            print("  bits : %s" % _short(bits_to_str(rx)))
            print("  texto: %s" % _short(repr(r["texto"])))
    return out


def plot_tdm(out_dir, sent, received, info):
    """Mapa dos slots (cabecalho, A, B) e posicoes com erro no payload."""
    from .evidence import C1, C2, CERR, INK2, _save, plt
    # O mapa vem do cabecalho recebido. Se o cabecalho chegou errado, ele
    # pode anunciar mais (ou menos) bits do que foram enviados: a figura
    # segue sempre o tamanho do que foi enviado.
    owner = np.concatenate([np.full(tdm.HEADER_BITS, 2), info["mapa"]])
    n = len(sent)
    if len(owner) < n:
        owner = np.concatenate([owner, np.full(n - len(owner), 2)])
    owner = owner[:n]
    rec = np.zeros(n, np.uint8)
    m = min(n, len(received))
    rec[:m] = received[:m]
    errs = np.flatnonzero(np.asarray(sent[:n]) != rec)
    fig, ax = plt.subplots(figsize=(7.5, 1.9))
    colors = {0: C1, 1: C2, 2: "#b9b8b3"}
    start = 0
    for j in range(1, n + 1):
        if j == n or owner[j] != owner[start]:
            ax.axvspan(start, j, ymin=0.35, ymax=0.95, color=colors[owner[start]],
                       linewidth=0, alpha=0.85)
            start = j
    for e in errs:
        ax.plot([e + 0.5], [0.15], "v", color=CERR, markersize=5)
    ax.set_xlim(0, n)
    ax.set_ylim(0, 1)
    ax.set_yticks([])
    ax.grid(False)
    ax.set_xlabel("indice do bit no payload TDM")
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color="#b9b8b3", label="cabecalho"),
                       Patch(color=C1, label="fluxo A"), Patch(color=C2, label="fluxo B")],
              loc="upper center", bbox_to_anchor=(0.5, 1.45), ncol=3)
    ax.set_title("Slots TDM (slot = %d bits); triangulos = bits errados antes do DEMUX (%d)"
                 % (info["cabecalho"]["slot"], len(errs)), color=INK2, pad=24)
    return _save(fig, out_dir, "tdm_slots.png")


def save_evidence(base, cenario, tcfg, rcfg, sent, payload, rx_info, tinfo,
                  fluxos, tx_audio=None, rx_audio=None, extra=None):
    from .evidence import make_evidence
    from .audio import write_wav
    d = _args.out_dir(base, cenario)
    os.makedirs(d, exist_ok=True)
    if rx_audio is not None:
        write_wav(os.path.join(d, "sinal_rx.wav"), rx_audio, rcfg.fa)
    if tx_audio is not None:
        write_wav(os.path.join(d, "sinal_tx.wav"), tx_audio, tcfg.fa)
    cmp_ = compare_bits(sent, payload)
    make_evidence(d, cenario, tcfg, rcfg, sent, rx_info, cmp_,
                  tx_audio=tx_audio, rx_audio=rx_audio, extra=extra)
    plot_tdm(d, sent, payload, tinfo)
    h = dict(tinfo["cabecalho"])
    rep = dict(cenario=cenario, cabecalho=h, completo=tinfo["completo"],
               bits_cabecalho=tdm.HEADER_BITS, bits_por_fluxo=tinfo["bits_por_fluxo"],
               fluxos=fluxos)
    with open(os.path.join(d, "tdm.json"), "w") as fh:
        json.dump(rep, fh, indent=2, ensure_ascii=True, default=_json_default)
    print("Evidencias em %s" % d)
    return d


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(type(o))


def _all_ok(fluxos):
    if not all(f["quadro_ok"] and f["cabecalho_ok"] for f in fluxos):
        return False
    return all(f.get("comparacao", {}).get("equal", f.get("crc_ok", True)) for f in fluxos)


# ----------------------------------------------------------------------
# Varias copias do quadro na mesma gravacao
# ----------------------------------------------------------------------
def best_frame(rx_info, threshold=0.9):
    """Escolhe, entre todas as copias do quadro na gravacao, a melhor.

    receive_bits() fica com o maior pico do SFD, que pode ser de uma copia
    cortada no fim da gravacao. Aqui cada pico acima do limiar e testado:
    vence a primeira copia com o cabecalho TDM e os dois fluxos passando no
    CRC; sem nenhuma assim, a que tiver mais CRCs ok. So usa os bits ja
    decididos pelo receptor (rx_info['raw_bits']); nao mexe na demodulacao.
    Devolve (payload, rx_info) com os campos do quadro escolhido.
    """
    bits = np.asarray(rx_info["raw_bits"], dtype=np.uint8)
    corr = rx_info["corr"]
    if len(corr) == 0:
        return rx_info["payload"], rx_info
    lim = threshold * len(SFD)
    peaks = [k for k in np.flatnonzero(np.abs(corr) >= lim)
             if abs(corr[k]) >= np.abs(corr[max(0, k - 16):k + 17]).max()]
    best, best_score = None, -1
    for k in peaks:
        inv = corr[k] < 0
        b = 1 - bits if inv else bits
        start = k + len(SFD)
        head = b[start:start + 8]
        if len(head) < 8:
            continue
        nbytes = int(bits_to_bytes(head)[0])
        pay = b[start + 8:start + 8 + 8 * nbytes]
        _, _, ti = tdm.demux(pay)
        score = int(ti["cabecalho_ok"]) + sum(int(f.get("crc_ok", False)) for f in ti["fluxos"])
        if ti["cabecalho_ok"] and not ti["completo"]:
            score -= 1
        if score > best_score:
            best_score = score
            best = dict(rx_info, payload=pay, nbytes=nbytes, sfd_index=int(k),
                        peak=float(corr[k]), inverted=bool(inv), ok=True, bits=b,
                        complete=len(pay) == 8 * nbytes)
        if score == 3 and ti["completo"]:
            break
    rx_info = dict(rx_info, copias=len(peaks))
    if best is None:
        return rx_info["payload"], rx_info
    best["copias"] = len(peaks)
    return best["payload"], best


# ----------------------------------------------------------------------
# Modos
# ----------------------------------------------------------------------
def run_simular(args):
    tcfg, rcfg = _args.tx_cfg(args), _args.rx_cfg(args)
    streams, descs = _streams_from_args(args)
    sent = tdm.mux(streams[0], streams[1], args.slot, not args.sem_fec)
    print("Fluxo A: %s | Fluxo B: %s" % (descs[0], descs[1]))
    print("Payload TDM: %d bits (cabecalho %d + slots %d)"
          % (len(sent), tdm.HEADER_BITS, len(sent) - tdm.HEADER_BITS))
    y_tx = transmit_bits(sent, tcfg)
    if args.ideal:
        y_rx = y_tx
    else:
        ch = ChannelConfig(gain=0.3, phase_rad=1.0, freq_offset_hz=0.5,
                           clock_ppm=100, ebn0_db=args.ebn0, seed=args.semente)
        y_rx = apply_channel(y_tx, tcfg.fa, tcfg.rb, ch)
    payload, rx_info = receive_bits(y_rx, rcfg)
    print_link(rx_info, ", %.2f s de audio" % (len(y_tx) / tcfg.fa))

    if args.erros:
        rng = np.random.default_rng(args.semente)
        pos = sorted(rng.choice(len(sent), size=min(args.erros, len(sent)),
                                replace=False).tolist())
        payload = flip_bits(payload, [p for p in pos if p < len(payload)])
        print("Erros injetados entre o enlace e o DEMUX nas posicoes %s" % pos)

    a, b, tinfo = tdm.demux(payload)
    fluxos = report_streams(streams, descs, [a, b], tinfo, rx_info=rx_info)
    if args.evidencias:
        save_evidence(args.evidencias, "sistema_simulacao", tcfg, rcfg, sent, payload,
                      rx_info, tinfo, fluxos, y_tx, y_rx,
                      extra=dict(tipo="simulacao", erros_injetados=args.erros,
                                 ebn0_db=None if args.ideal else args.ebn0))
    return 0 if _all_ok(fluxos) else 1


def run_tx(args):
    from .audio import play, write_wav
    tcfg = _args.tx_cfg(args)
    streams, descs = _streams_from_args(args)
    sent = tdm.mux(streams[0], streams[1], args.slot, not args.sem_fec)
    y = transmit_bits(sent, tcfg)
    print("Fluxo A: %s | Fluxo B: %s" % (descs[0], descs[1]))
    print("Payload TDM: %d bits, sinal de %.2f s" % (len(sent), len(y) / tcfg.fa))
    gap = np.zeros(int(args.pausa * tcfg.fa))
    sig = np.concatenate([np.concatenate([gap, y]) for _ in range(args.repetir)] + [gap])
    if args.wav:
        write_wav(args.wav, sig, tcfg.fa)
        print("WAV salvo em %s (%d copia(s) do quadro, %.1f s)"
              % (args.wav, args.repetir, len(sig) / tcfg.fa))
    if args.tocar:
        play(sig, tcfg.fa, args.device)
    if not (args.wav or args.tocar):
        print("(use --tocar e/ou --wav)")
    return 0


def run_rx(args):
    from .audio import read_wav, record_until_signal
    from .config import TxConfig
    rcfg = _args.rx_cfg(args)
    if args.wav:
        y, _ = read_wav(args.wav, rcfg.fa)
    else:
        y, ns = record_until_signal(args.gravar, rcfg.fa, args.nivel, device=args.device)
        print("Valor de deteccao do sinal: %.3f" % ns)
    payload, rx_info = receive_bits(y, rcfg)
    payload, rx_info = best_frame(rx_info, rcfg.sfd_threshold)
    print_link(rx_info)
    a, b, tinfo = tdm.demux(payload)
    expected, descs = _streams_from_args(args, prefix="esperado-")
    has_exp = any(e is not None for e in expected)
    fluxos = report_streams(expected if has_exp else None, descs, [a, b], tinfo,
                            rx_info=rx_info)
    if args.evidencias:
        if not all(e is not None for e in expected):
            raise SystemExit("--evidencias precisa do esperado dos dois fluxos")
        sent = tdm.mux(expected[0], expected[1], tinfo["cabecalho"]["slot"],
                       tinfo["cabecalho"]["fec"])
        save_evidence(args.evidencias, args.cenario, TxConfig(rb=rcfg.rb, fp=rcfg.fp, fa=rcfg.fa),
                      rcfg, sent, payload, rx_info, tinfo, fluxos, rx_audio=y,
                      extra=dict(origem=args.wav or "microfone"))
    return 0 if rx_info["ok"] and _all_ok(fluxos) else 1


def run_acustico(args):
    from .audio import play_and_record
    tcfg, rcfg = _args.tx_cfg(args), _args.rx_cfg(args)
    streams, descs = _streams_from_args(args)
    sent = tdm.mux(streams[0], streams[1], args.slot, not args.sem_fec)
    y_tx = transmit_bits(sent, tcfg)
    print("Fluxo A: %s | Fluxo B: %s" % (descs[0], descs[1]))
    print("Tocando e gravando %.2f s..." % (len(y_tx) / tcfg.fa))
    y_rx = play_and_record(y_tx, tcfg.fa, 0.5, 1.0, args.device)
    if len(y_rx) == 0:
        raise SystemExit("A gravacao voltou vazia: o microfone nao entregou nenhuma amostra.")
    print("Pico gravado: %.3f" % float(np.max(np.abs(y_rx))))
    payload, rx_info = receive_bits(y_rx, rcfg)
    print_link(rx_info)
    a, b, tinfo = tdm.demux(payload)
    fluxos = report_streams(streams, descs, [a, b], tinfo, rx_info=rx_info)
    save_evidence(args.evidencias, "sistema_acustico_1maquina", tcfg, rcfg, sent, payload,
                  rx_info, tinfo, fluxos, y_tx, y_rx)
    return 0 if _all_ok(fluxos) else 1


def main(argv=None):
    p = argparse.ArgumentParser(description="Sistema completo: CRC + Hamming + TDM + BPSK")
    sub = p.add_subparsers(dest="modo", required=True)

    s = sub.add_parser("simular", help="simulacao por software")
    _add_streams(s)
    _add_tdm_args(s)
    _args.add_link_args(s)
    _args.add_rx_args(s)
    s.add_argument("--ideal", action="store_true", help="sem canal (TX direto no RX)")
    s.add_argument("--ebn0", type=float, default=12.0, help="Eb/N0 do canal (dB)")
    s.add_argument("--erros", type=int, default=0,
                   help="inverte N bits sorteados do payload antes do DEMUX")
    s.add_argument("--semente", type=int, default=1)
    s.add_argument("--evidencias", metavar="DIR")
    s.set_defaults(func=run_simular)

    t = sub.add_parser("tx", help="transmissor")
    _add_streams(t)
    _add_tdm_args(t)
    _args.add_link_args(t)
    t.add_argument("--wav")
    t.add_argument("--tocar", action="store_true")
    t.add_argument("--repetir", type=int, default=1)
    t.add_argument("--pausa", type=float, default=1.0)
    t.set_defaults(func=run_tx)

    r = sub.add_parser("rx", help="receptor")
    src = r.add_mutually_exclusive_group(required=True)
    src.add_argument("--wav")
    src.add_argument("--gravar", type=float, metavar="S")
    r.add_argument("--nivel", type=float, default=0.1)
    r.add_argument("--evidencias", metavar="DIR")
    r.add_argument("--cenario", default="sistema_2maquinas")
    _add_streams(r, prefix="esperado-")
    _args.add_link_args(r)
    _args.add_rx_args(r)
    r.set_defaults(func=run_rx)

    a = sub.add_parser("acustico", help="toca e grava numa maquina so")
    _add_streams(a)
    _add_tdm_args(a)
    _args.add_link_args(a)
    _args.add_rx_args(a)
    a.add_argument("--evidencias", default="evidencias", metavar="DIR")
    a.set_defaults(func=run_acustico)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
