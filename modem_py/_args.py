"""Opcoes de linha de comando comuns aos scripts."""

import os
import time

from .config import RxConfig, TxConfig
from .framing import text_to_bits
from .seq import prbs7, str_to_bits

DEFAULT_PRBS = 64


def add_payload_args(p, prefix=""):
    """--texto / --prbs / --bits (com prefixo 'esperado-' no receptor)."""
    g = p.add_mutually_exclusive_group()
    g.add_argument("--%stexto" % prefix, help="mensagem de texto (como o tx.m)")
    g.add_argument("--%sprbs" % prefix, type=int, metavar="N",
                   help="N bits da PRBS-7 (padrao do transmissor: %d)" % DEFAULT_PRBS)
    g.add_argument("--%sbits" % prefix, metavar="0101...",
                   help="sequencia de bits explicita")


def payload_from_args(args, prefix="", default_prbs=None):
    """Retorna (bits, descricao) ou (None, None) se nada foi pedido."""
    key = prefix.replace("-", "_")
    texto = getattr(args, key + "texto")
    nprbs = getattr(args, key + "prbs")
    bits = getattr(args, key + "bits")
    if texto is not None:
        return text_to_bits(texto), "texto: %r" % texto
    if bits is not None:
        return str_to_bits(bits), "bits explicitos (%d)" % len(str_to_bits(bits))
    if nprbs is None:
        nprbs = default_prbs
    if nprbs is None:
        return None, None
    return prbs7(nprbs), "PRBS-7, %d bits" % nprbs


def add_link_args(p):
    p.add_argument("--rb", type=float, default=TxConfig.rb, help="taxa de bits (bit/s)")
    p.add_argument("--fp", type=float, default=TxConfig.fp, help="portadora (Hz)")
    p.add_argument("--fa", type=int, default=TxConfig.fa, help="amostragem (Hz)")
    p.add_argument("--device", default=None, help="dispositivo de audio (sounddevice)")


def add_rx_args(p):
    p.add_argument("--professor", action="store_true",
                   help="receptor identico ao receptor_2.m (sem passa-faixa, AGC e passa-baixas)")


def tx_cfg(args):
    return TxConfig(rb=args.rb, fp=args.fp, fa=args.fa)


def rx_cfg(args):
    kw = dict(rb=args.rb, fp=args.fp, fa=args.fa)
    return RxConfig.professor(**kw) if args.professor else RxConfig(**kw)


def out_dir(base, name):
    return os.path.join(base, "%s_%s" % (name, time.strftime("%Y%m%d_%H%M%S")))
