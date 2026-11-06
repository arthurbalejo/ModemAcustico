# Modem acústico: enlace básico em Python

UFSM00050 Comunicação de Dados, 2026/2. Porte para Python do código-base `modem_acustico.zip` (MATLAB/Octave):
BPSK, 100 bit/s, portadora de 2 kHz, amostragem de 8 kHz, cosseno levantado r = 0,5, preâmbulo + SFD de 32 bits,
laço de Costas, sincronização cedo-tarde e correlação com o SFD.

Repositório: https://github.com/arthurbalejo/ModemAcustico

## Pontos de entrada
| | Comando | Função Python |
|---|---|---|
| Transmissor | `python -m modem_py.tx` | `modem_py.transmitter.transmit_bits(bits) -> audio` |
| Receptor | `python -m modem_py.rx` | `modem_py.receiver.receive_bits(audio) -> (bits, info)` |
| Simulação | `python -m modem_py.simular` | |
| Acústico em 1 máquina | `python -m modem_py.acustico` | |

## Início rápido
```bash
git clone https://github.com/arthurbalejo/ModemAcustico.git
cd ModemAcustico
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q                       # testes
.venv/bin/python -m modem_py.simular                # simulação + evidências em evidencias/
.venv/bin/python -m modem_py.acustico --prbs 64     # alto-falante -> microfone
```
Duas máquinas: `rx --gravar 5 --esperado-prbs 64 --evidencias evidencias` no receptor e `tx --prbs 64 --tocar` no transmissor.

A documentação completa está em `docs/`, um vault do Obsidian: comece por `docs/00 - Índice.md`.
