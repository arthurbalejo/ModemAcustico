"""Ponto de entrada do transmissor (equivale ao tx.m).

Exemplos:
    python -m modem_py.tx --prbs 64 --tocar
    python -m modem_py.tx --texto OLA --wav sinal_tx.wav
"""

import argparse

import numpy as np

from . import _args
from .audio import play, write_wav
from .framing import build_frame
from .seq import bits_to_str
from .transmitter import transmit_bits


def main(argv=None):
    p = argparse.ArgumentParser(description="Transmissor BPSK (modem acustico)")
    _args.add_payload_args(p)
    _args.add_link_args(p)
    p.add_argument("--tocar", action="store_true", help="toca na placa de som")
    p.add_argument("--wav", help="salva o sinal em WAV")
    p.add_argument("--repetir", type=int, default=1, help="toca N vezes")
    p.add_argument("--pausa", type=float, default=1.0, help="silencio entre repeticoes (s)")
    args = p.parse_args(argv)

    cfg = _args.tx_cfg(args)
    bits, desc = _args.payload_from_args(args, default_prbs=_args.DEFAULT_PRBS)
    y = transmit_bits(bits, cfg)
    frame = build_frame(bits)

    print("Payload: %s" % desc)
    print("Bits do payload: %s" % bits_to_str(bits))
    print("Tamanho do quadro: %d bits" % len(frame))
    print("Tamanho do sinal: %d amostras (%.2f s)" % (len(y), len(y) / cfg.fa))

    if args.wav:
        write_wav(args.wav, y, cfg.fa)
        print("WAV salvo em %s" % args.wav)
    if args.tocar:
        gap = np.zeros(int(args.pausa * cfg.fa))
        sig = np.concatenate([np.concatenate([y, gap]) for _ in range(args.repetir)])
        print("Tocando %d vez(es)..." % args.repetir)
        play(sig, cfg.fa, args.device)
    if not (args.wav or args.tocar):
        print("(use --tocar e/ou --wav)")


if __name__ == "__main__":
    main()
