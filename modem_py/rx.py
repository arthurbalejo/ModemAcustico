"""Ponto de entrada do receptor (equivale ao rx.m).

Exemplos:
    python -m modem_py.rx --gravar 5 --esperado-prbs 64 --evidencias evidencias
    python -m modem_py.rx --wav captura.wav --esperado-texto OLA
"""

import argparse
import os

from . import _args
from .audio import read_wav, record_until_signal, write_wav
from .evidence import make_evidence
from .framing import bits_to_text
from .receiver import receive_bits
from .seq import bits_to_str, compare_bits


def main(argv=None):
    p = argparse.ArgumentParser(description="Receptor BPSK (modem acustico)")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--wav", help="le o sinal de um arquivo WAV")
    src.add_argument("--gravar", type=float, metavar="S",
                     help="grava blocos de S segundos ate detectar sinal (t_captura)")
    p.add_argument("--nivel", type=float, default=0.1,
                   help="nivel minimo de deteccao, NS_min do rx.m (padrao 0.1)")
    p.add_argument("--salvar-wav", help="salva a captura em WAV")
    p.add_argument("--evidencias", metavar="DIR",
                   help="gera figuras e relatorio.json em DIR/<cenario>_<data>")
    p.add_argument("--cenario", default="acustico_2maquinas",
                   help="nome do cenario no relatorio")
    _args.add_payload_args(p, prefix="esperado-")
    _args.add_link_args(p)
    _args.add_rx_args(p)
    args = p.parse_args(argv)

    cfg = _args.rx_cfg(args)
    if args.wav:
        y, _ = read_wav(args.wav, cfg.fa)
        print("Lido %s: %d amostras" % (args.wav, len(y)))
    else:
        y, ns = record_until_signal(args.gravar, cfg.fa, args.nivel, device=args.device)
        print("Valor de deteccao do sinal: %.3f" % ns)
        if args.salvar_wav:
            write_wav(args.salvar_wav, y, cfg.fa)

    payload, info = receive_bits(y, cfg)
    if not info["ok"]:
        print("Muitos erros para decodificar os dados (pico SFD = %.0f/32)" % info["peak"])
    print("SFD: pico %.0f/32 no bit %d, polaridade invertida: %s"
          % (info["peak"], info["sfd_index"], info["inverted"]))
    print("Tamanho da mensagem recebida: %d bytes" % info["nbytes"])
    print("Bits recebidos: %s" % bits_to_str(payload))
    print("Como texto: %r" % bits_to_text(payload))

    expected, desc = _args.payload_from_args(args, prefix="esperado-")
    cmp_ = None
    if expected is not None:
        cmp_ = compare_bits(expected, payload)
        print("Comparacao com %s: %d erros em %d bits (BER = %.4g)"
              % (desc, cmp_["n_errors"], cmp_["n_sent"], cmp_["ber"]))
        if cmp_["error_positions"]:
            print("Posicoes com erro: %s" % cmp_["error_positions"])

    if args.evidencias:
        if expected is None:
            p.error("--evidencias precisa de --esperado-texto/--esperado-prbs/--esperado-bits")
        d = _args.out_dir(args.evidencias, args.cenario)
        os.makedirs(d, exist_ok=True)
        write_wav(os.path.join(d, "sinal_rx.wav"), y, cfg.fa)
        from .config import TxConfig
        make_evidence(d, args.cenario, TxConfig(rb=cfg.rb, fp=cfg.fp, fa=cfg.fa),
                      cfg, expected, info, cmp_, rx_audio=y,
                      extra=dict(payload=desc, origem=args.wav or "microfone"))
        print("Evidencias em %s" % d)
    return 0 if (cmp_ is None and info["ok"]) or (cmp_ and cmp_["equal"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
