"""Testes T11 a T14 (CRC-8 e Hamming (7,4)) com evidencias para o relatorio.

Tudo em software: os erros sao introduzidos de forma controlada nos bits,
sem passar pela modulacao nem pelo canal acustico.

Gera em evidencias/fec/:
    resumo.json                     tabelas de T11 a T14
    t12_exemplo.txt                 exemplo bit a bit de uma correcao
    t13_exemplo.txt                 exemplo de 2 erros num bloco (CRC acusa)
    t14_ber.png                     BER antes x depois do CRC + Hamming
    t14_exemplo_bits.png            fluxo com erros injetados e corrigidos

Exemplo:
    python -m modem_py.testes_fec
    python -m modem_py.testes_fec --rapido
"""

import argparse
import itertools
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from .channel import flip_bits  # noqa: E402
from .evidence import C1, C2, C3, CERR, INK2  # noqa: E402
from .fec import (crc8, crc8_check, crc8_encode, hamming74_decode,  # noqa: E402
                  hamming74_encode, hamming74_syndrome, protect, recover)
from .framing import bits_to_text, bytes_to_bits, text_to_bits  # noqa: E402
from .seq import bits_to_str, compare_bits  # noqa: E402


def grupos(bits, n):
    s = bits_to_str(bits)
    return " ".join(s[i:i + n] for i in range(0, len(s), n))


# ----------------------------------------------------------------------
# T11
# ----------------------------------------------------------------------
def t11(rng, casos, nbytes_lista=(8, 32)):
    """CRC-8: taxa de deteccao com 0..3 erros em posicoes sorteadas."""
    linhas = []
    for nbytes in nbytes_lista:
        for nerr in (0, 1, 2, 3):
            detectados = 0
            for _ in range(casos):
                tx = crc8_encode(rng.integers(0, 2, 8 * nbytes).astype(np.uint8))
                pos = rng.choice(len(tx), nerr, replace=False) if nerr else []
                if not crc8_check(flip_bits(tx, pos)):
                    detectados += 1
            linhas.append(dict(bytes_dados=nbytes, erros=nerr, casos=casos,
                               rejeitados=detectados,
                               taxa=detectados / casos))
            print("  T11  %2d bytes  %d erros: %4d/%d rejeitados (%.1f%%)"
                  % (nbytes, nerr, detectados, casos, 100 * detectados / casos))
    # Pares exaustivos: no limite da distancia 4 (119 bits) e acima dele
    pares = []
    for nbits in (119, 256):
        tx = crc8_encode(rng.integers(0, 2, nbits).astype(np.uint8))
        total = falhas = 0
        for i, j in itertools.combinations(range(len(tx)), 2):
            total += 1
            falhas += int(crc8_check(flip_bits(tx, [i, j])))
        pares.append(dict(bits_dados=nbits, pares=total, nao_detectados=falhas))
        print("  T11  todos os pares em %d bits de dados: %d de %d nao detectados"
              % (nbits, falhas, total))
    # Exemplo controlado
    msg = text_to_bits("UFSM")
    tx = crc8_encode(msg)
    rx = flip_bits(tx, [5])
    exemplo = dict(mensagem="UFSM", bits=grupos(msg, 8), crc=bits_to_str(crc8(msg)),
                   erro_na_posicao=5, crc_ok_sem_erro=bool(crc8_check(tx)),
                   crc_ok_com_erro=bool(crc8_check(rx)),
                   resto_com_erro=bits_to_str(crc8(rx)))
    print("  T11  exemplo 'UFSM': CRC=%s, sem erro ok=%s, bit 5 trocado ok=%s (resto %s)"
          % (exemplo["crc"], exemplo["crc_ok_sem_erro"], exemplo["crc_ok_com_erro"],
             exemplo["resto_com_erro"]))
    return dict(taxas=linhas, pares_exaustivos=pares, exemplo=exemplo)


# ----------------------------------------------------------------------
# T12
# ----------------------------------------------------------------------
def t12(out_dir):
    corrigidos = total = 0
    for d in range(16):
        data = np.array([(d >> i) & 1 for i in range(4)], dtype=np.uint8)
        code = hamming74_encode(data)
        for pos in range(7):
            rx = flip_bits(code, [pos])
            out, info = hamming74_decode(rx)
            total += 1
            if (out.tolist() == data.tolist() and hamming74_syndrome(rx) == pos + 1
                    and info["posicoes"] == [pos]):
                corrigidos += 1
    print("  T12  1 erro em cada posicao x 16 palavras: %d de %d corrigidos"
          % (corrigidos, total))

    # Exemplo legivel: "UFSM", um erro em 3 blocos diferentes
    msg = text_to_bits("UFSM")
    code = hamming74_encode(msg)
    pos = [3, 20, 50]
    rx = flip_bits(code, pos)
    out, info = hamming74_decode(rx)
    txt = "\n".join([
        "T12 - Hamming (7,4) corrige 1 erro por bloco (simulacao por software)",
        "Mensagem: 'UFSM' (%d bits, LSB primeiro)" % len(msg),
        "Dados        : %s" % grupos(msg, 4),
        "Codificado   : %s" % grupos(code, 7),
        "Erros nas posicoes %s (blocos %s)" % (pos, [p // 7 for p in pos]),
        "Recebido     : %s" % grupos(rx, 7),
        "Sindromes    : %s" % info["sindromes"],
        "Corrigidos   : %d blocos, posicoes %s" % (info["corrigidos"], info["posicoes"]),
        "Decodificado : %s" % grupos(out, 4),
        "Texto        : %r  (igual ao original: %s)"
        % (bits_to_text(out), out.tolist() == msg.tolist()),
    ])
    with open(os.path.join(out_dir, "t12_exemplo.txt"), "w") as fh:
        fh.write(txt + "\n")
    return dict(casos=total, corrigidos=corrigidos,
                exemplo=dict(posicoes_erro=pos, sindromes=info["sindromes"],
                             corrigidos=info["posicoes"],
                             recuperado=out.tolist() == msg.tolist()))


# ----------------------------------------------------------------------
# T13
# ----------------------------------------------------------------------
def t13(out_dir):
    msg = bytes_to_bits([0xA5])
    coded = protect(msg)
    ref, _ = hamming74_decode(coded)
    total = errado = crc_acusou = 0
    for blk in range(len(coded) // 7):
        for i, j in itertools.combinations(range(7), 2):
            rx = flip_bits(coded, [7 * blk + i, 7 * blk + j])
            data, _ = hamming74_decode(rx)
            _, info = recover(rx, 8)
            total += 1
            errado += int(data.tolist() != ref.tolist())
            crc_acusou += int(not info["crc_ok"])
    print("  T13  2 erros no mesmo bloco: %d casos, %d decodificados errado, CRC acusou %d"
          % (total, errado, crc_acusou))

    rx = flip_bits(coded, [0, 4])
    data, hinfo = hamming74_decode(rx)
    out, info = recover(rx, 8)
    txt = "\n".join([
        "T13 - limite do Hamming (7,4): 2 erros no mesmo bloco (simulacao por software)",
        "Dados (0xA5) + CRC-8: %s" % grupos(ref, 4),
        "Codificado          : %s" % grupos(coded, 7),
        "Erros nas posicoes [0, 4] (bloco 0)",
        "Recebido            : %s" % grupos(rx, 7),
        "Sindrome do bloco 0 : %d -> o decodificador troca o bit %d (errado)"
        % (hinfo["sindromes"][0], hinfo["sindromes"][0] - 1),
        "Decodificado        : %s" % grupos(data, 4),
        "Bits de dados errados: %s" % compare_bits(ref, data)["error_positions"],
        "CRC-8 ok            : %s  -> erro nao corrigido detectado" % info["crc_ok"],
    ])
    with open(os.path.join(out_dir, "t13_exemplo.txt"), "w") as fh:
        fh.write(txt + "\n")
    return dict(casos=total, decodificados_errado=errado, crc_acusou=crc_acusou)


# ----------------------------------------------------------------------
# T14
# ----------------------------------------------------------------------
def t14(rng, out_dir, mensagens):
    nbytes = 32
    pontos = [1e-3, 2e-3, 5e-3, 1e-2, 2e-2, 5e-2, 1e-1]
    linhas = []
    for p in pontos:
        err_in = err_out = erradas = detectadas = 0
        for _ in range(mensagens):
            msg = rng.integers(0, 2, 8 * nbytes).astype(np.uint8)
            coded = protect(msg)
            mask = (rng.random(len(coded)) < p).astype(np.uint8)
            out, info = recover(coded ^ mask, len(msg))
            nerr = int((out != msg).sum())
            err_in += int(mask.sum())
            err_out += nerr
            if nerr:
                erradas += 1
                detectadas += int(not info["crc_ok"])
        nbits_c = len(protect(np.zeros(8 * nbytes, np.uint8)))
        # Sem codigo: mesma BER de canal direto nos dados
        linhas.append(dict(ber_injetada=p,
                           ber_medida_canal=err_in / (mensagens * nbits_c),
                           ber_residual=err_out / (mensagens * 8 * nbytes),
                           mensagens=mensagens, mensagens_erradas=erradas,
                           erradas_detectadas_crc=detectadas,
                           erradas_nao_detectadas=erradas - detectadas))
        print("  T14  p=%.0e  BER canal=%.2e  residual=%.2e  msgs erradas=%d/%d  CRC acusou %d"
              % (p, linhas[-1]["ber_medida_canal"], linhas[-1]["ber_residual"],
                 erradas, mensagens, detectadas))

    fig, ax = plt.subplots(figsize=(5.6, 3.8))
    x = np.array(pontos)
    ax.loglog(x, x, color=INK2, linestyle="--", label="sem codigo (BER = p)")
    # Aproximacao: bloco com >= 2 erros em 7 erra ~3 bits dos 7 -> ~ (3/7) dos dados
    pb = 1 - (1 - x) ** 7 - 7 * x * (1 - x) ** 6
    ax.loglog(x, pb * 3 / 7, color=C3, linestyle=":", label="Hamming (7,4) aprox.")
    res = np.array([r["ber_residual"] for r in linhas])
    floor = 0.5 / (mensagens * 8 * nbytes)
    ax.loglog(x, np.maximum(res, floor), "o-", color=C1, markersize=5,
              label="CRC + Hamming (medida)")
    ax.set_xlabel("BER injetada no canal p")
    ax.set_ylabel("BER dos dados apos decodificar")
    ax.set_title("T14: %d mensagens de %d bytes por ponto" % (mensagens, nbytes))
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "t14_ber.png"), dpi=150)
    plt.close(fig)

    # Exemplo de um fluxo: erros isolados (corrigidos) + um bloco com 2 erros
    msg = text_to_bits("UFSM")
    coded = protect(msg)
    pos = [3, 20, 29, 31, 50]          # 29 e 31 no mesmo bloco (4, bits de dados)
    rx = flip_bits(coded, pos)
    out, info = recover(rx, len(msg))
    cmp_ = compare_bits(msg, out)
    fig, axes = plt.subplots(3, 1, figsize=(7.4, 3.8), sharex=False)
    for ax, bits, title, errs, color in (
            (axes[0], coded, "codificado (CRC + Hamming), %d bits" % len(coded), [], C1),
            (axes[1], rx, "recebido: erros injetados nas posicoes %s" % pos, pos, C2),
            (axes[2], out, "decodificado (%d bits): %d erros, CRC ok = %s"
             % (len(msg), cmp_["n_errors"], info["crc_ok"]),
             cmp_["error_positions"], C1)):
        xx = np.arange(len(bits))
        ax.step(xx, bits, where="post", color=color)
        for e in errs:
            ax.axvspan(e, e + 1, color=CERR, alpha=0.4, linewidth=0)
        ax.set_ylim(-0.3, 1.3)
        ax.set_yticks([0, 1])
        ax.set_title(title, fontsize=9)
    axes[2].set_xlabel("indice do bit")
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "t14_exemplo_bits.png"), dpi=150)
    plt.close(fig)
    print("  T14  exemplo 'UFSM' com erros em %s: %d corrigidos, %d erros restantes, CRC ok=%s"
          % (pos, info["corrigidos"], cmp_["n_errors"], info["crc_ok"]))
    return dict(nbytes=nbytes, pontos=linhas,
                exemplo=dict(posicoes_erro=pos, corrigidos=info["corrigidos"],
                             erros_restantes=cmp_["n_errors"], crc_ok=info["crc_ok"]))


def main(argv=None):
    p = argparse.ArgumentParser(description="Testes T11-T14: CRC-8 e Hamming (7,4)")
    p.add_argument("--saida", default="evidencias")
    p.add_argument("--rapido", action="store_true")
    args = p.parse_args(argv)
    out_dir = os.path.join(args.saida, "fec")
    os.makedirs(out_dir, exist_ok=True)
    rng = np.random.default_rng(2026)
    casos = 200 if args.rapido else 1000
    resumo = dict(
        tipo="simulacao por software (erros injetados nos bits, sem canal acustico)",
        crc="CRC-8, g(x) = x^8 + x^2 + x + 1 (0x07), inicio 0, sem reflexao",
        hamming="Hamming (7,4), p1 p2 d1 p3 d2 d3 d4",
        T11=t11(rng, casos),
        T12=t12(out_dir),
        T13=t13(out_dir),
        T14=t14(rng, out_dir, 200 if args.rapido else 2000),
    )
    with open(os.path.join(out_dir, "resumo.json"), "w") as fh:
        json.dump(resumo, fh, indent=2)
    print("Evidencias em %s" % out_dir)


if __name__ == "__main__":
    main()
