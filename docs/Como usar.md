---
tags: [modem-acustico, uso]
---
# Como usar

Voltar: [[00 - Índice]]

Todos os comandos rodam a partir da pasta `enlaceBasico/`.

## Instalação
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q          # 17 testes, ~3 s
```
O `sounddevice` precisa da PortAudio (no Fedora: `sudo dnf install portaudio`). Sem ela, a simulação e o modo WAV funcionam mesmo assim.
Para listar os dispositivos de áudio: `.venv/bin/python -m sounddevice`. Para escolher um, use `--device N` em qualquer comando.

## 1. Simulação por software
```bash
.venv/bin/python -m modem_py.simular            # ~1 min (curva de BER completa)
.venv/bin/python -m modem_py.simular --rapido   # ~20 s
```
Gera `evidencias/simulacao/{extras,professor}/<cenário>/` (figuras + `relatorio.json`), `ber.png`, `ber.json` e `resumo.json`. Também decodifica as gravações do zip, se `../modem_acustico/sinal/` existir, em `evidencias/wav_professor/`.

## 2. Acústico numa máquina só
Alto-falante e microfone do mesmo notebook. Volume em ~70%, sem fone de ouvido, ambiente silencioso.
```bash
.venv/bin/python -m modem_py.acustico --prbs 64
.venv/bin/python -m modem_py.acustico --texto "UFSM" --professor   # receptor original
```
O comando toca e grava ao mesmo tempo (`sounddevice.playrec`), decodifica e salva tudo em `evidencias/acustico_1maquina_<data>/`: `sinal_tx.wav`, `sinal_rx.wav`, figuras e `relatorio.json`.

## 3. Acústico em duas máquinas
**Máquina RX** (começa primeiro, fica esperando o sinal):
```bash
.venv/bin/python -m modem_py.rx --gravar 5 --nivel 0.05 \
    --esperado-prbs 64 --evidencias evidencias
```
**Máquina TX:**
```bash
.venv/bin/python -m modem_py.tx --prbs 64 --tocar
```
- `--gravar 5`: blocos de 5 s. O quadro de 64 bits dura 1,84 s, então o bloco precisa ser bem maior que isso, porque o quadro pode começar no meio de um bloco. Se não decodificar, aumente o bloco ou toque com `--repetir 3`.
- `--nivel`: equivale ao `NS_min` do `rx.m`. Abaixe se o microfone captar baixo.
- As evidências vão para `evidencias/acustico_2maquinas_<data>/`, junto com o WAV capturado.

## 4. Via arquivo WAV
Serve quando a placa de som de uma das máquinas não funciona com o Python, ou para gravar com outro programa (celular, Audacity):
```bash
.venv/bin/python -m modem_py.tx --prbs 64 --wav sinal_tx.wav      # gera o WAV (8 kHz, 16 bits)
# toque o sinal_tx.wav em qualquer player e grave do outro lado (8 kHz ou qualquer taxa)
.venv/bin/python -m modem_py.rx --wav captura.wav --esperado-prbs 64 \
    --evidencias evidencias --cenario acustico_wav
```
O `rx` reamostra para 8 kHz se a gravação vier em outra taxa (por exemplo, 44,1 kHz do celular).

## Opções úteis
| Opção | Onde | O que faz |
|---|---|---|
| `--texto T` / `--prbs N` / `--bits 0101…` | tx, acustico | payload (padrão: PRBS-7 com 64 bits) |
| `--esperado-texto/-prbs/-bits` | rx | sequência para comparar e calcular a BER |
| `--professor` | rx, acustico | receptor idêntico ao `receptor_2.m` |
| `--rb`, `--fp`, `--fa` | todos | parâmetros do enlace (TX e RX iguais!) |
| `--repetir N` | tx | toca o quadro N vezes com 1 s de pausa |

## Depois de uma execução
- Copie as figuras que vão para o relatório para `docs/figuras/`. O Obsidian só enxerga arquivos dentro do vault.
- Preencha [[Resultados#Transmissão acústica]] com os números do `relatorio.json`.
