"""Enlace acustico numa maquina so: toca no alto-falante e grava no microfone.

Exemplo:
    python -m modem_py.acustico --prbs 64
    python -m modem_py.acustico --texto OLA --professor
"""

import argparse
import os

from . import _args
from .audio import play_and_record, write_wav
from .evidence import make_evidence
from .receiver import receive_bits
from .seq import bits_to_str, compare_bits
from .transmitter import transmit_bits


def main(argv=None):
    p = argparse.ArgumentParser(description="Teste acustico em uma maquina")
    _args.add_payload_args(p)
    _args.add_link_args(p)
    _args.add_rx_args(p)
    p.add_argument("--evidencias", default="evidencias", metavar="DIR")
    p.add_argument("--antes", type=float, default=0.5, help="silencio antes (s)")
    p.add_argument("--depois", type=float, default=1.0, help="silencio depois (s)")
    args = p.parse_args(argv)

    tcfg, rcfg = _args.tx_cfg(args), _args.rx_cfg(args)
    bits, desc = _args.payload_from_args(args, default_prbs=_args.DEFAULT_PRBS)
    y_tx = transmit_bits(bits, tcfg)
    print("Payload: %s (%d bits), sinal de %.2f s" % (desc, len(bits), len(y_tx) / tcfg.fa))
    print("Tocando e gravando...")
    y_rx = play_and_record(y_tx, tcfg.fa, args.antes, args.depois, args.device)
    print("Pico gravado: %.3f" % abs(y_rx).max())

    payload, info = receive_bits(y_rx, rcfg)
    cmp_ = compare_bits(bits, payload)
    print("SFD: pico %.0f/32, invertido: %s, bytes: %d"
          % (info["peak"], info["inverted"], info["nbytes"]))
    print("Enviados : %s" % bits_to_str(bits))
    print("Recebidos: %s" % bits_to_str(payload))
    print("%d erros em %d bits (BER = %.4g)" % (cmp_["n_errors"], cmp_["n_sent"], cmp_["ber"]))

    d = _args.out_dir(args.evidencias, "acustico_1maquina")
    os.makedirs(d, exist_ok=True)
    write_wav(os.path.join(d, "sinal_tx.wav"), y_tx, tcfg.fa)
    write_wav(os.path.join(d, "sinal_rx.wav"), y_rx, tcfg.fa)
    make_evidence(d, "acustico_1maquina", tcfg, rcfg, bits, info, cmp_,
                  tx_audio=y_tx, rx_audio=y_rx, extra=dict(payload=desc))
    print("Evidencias em %s" % d)
    return 0 if cmp_["equal"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
