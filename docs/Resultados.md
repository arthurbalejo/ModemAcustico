---
tags: [modem-acustico, resultados]
---
# Resultados

Voltar: [[00 - Índice]] · Testes: [[Plano de testes]]

> [!important] Separação exigida pela especificação
> Os resultados estão em três grupos que **não se misturam**:
> 1. **Simulação por software**: canal modelado em `channel.py`, sem som.
> 2. **Gravações acústicas do código-base**: WAVs que vêm no `modem_acustico.zip`, gravados pelo professor e decodificados pelo nosso porte. É transmissão acústica real, mas não foi feita pela equipe.
> 3. **Transmissão acústica da equipe**: alto-falante → microfone, feita por nós. *A preencher após a demonstração.*

---

## 1. Simulação por software

Gerado com `python -m modem_py.simular` em 02/11/2026. Os arquivos estão em `evidencias/simulacao/`.
Payload: PRBS-7, 64 bits. Quadro: 184 bits = 1,84 s.

### Cenários

| Cenário | Canal | Receptor com extras | Receptor original (`receptor_2.m`) |
|---|---|---|---|
| ideal | TX ligado direto no RX (como o `teste.m`) | **0/64 erros**, SFD 32/32 | **0/64**, SFD 32/32 |
| realista | 0,5 s de atraso, ganho 0,3, fase 1 rad, desvio de 0,5 Hz, relógio 100 ppm, $E_b/N_0$ = 12 dB | **0/64**, SFD 32/32, SNR na decisão 12,3 dB | 32/64, SFD −14 (quadro não encontrado) |
| fase_180 | portadora girada 180°, $E_b/N_0$ = 15 dB | **0/64**, SFD −32 → polaridade corrigida | 11/64, SFD −28 |
| ruidoso | fase 2 rad, desvio de 1 Hz, relógio 200 ppm, $E_b/N_0$ = 6 dB | **0/64**, SFD −32 (corrigido), SNR 7,9 dB | 30/64, SFD 16 |

Cada efeito isolado sobre o receptor original, com 64 bits:

| Efeito | Erros |
|---|---|
| só ganho 0,3 | 10 |
| só desvio de 0,5 Hz | 17 |
| fase de 1 rad | 0 |
| relógio 100 ppm | 0 |

Com os extras, os quatro casos dão 0 erros. A explicação está em [[Receptor#Extras]].

### Figuras do cenário realista (receptor com extras)

![[sim_realista_bits_enviados_recebidos.png]]
![[sim_realista_correlacao_sfd.png]]
![[sim_realista_olho.png]]
![[sim_realista_constelacao.png]]
![[sim_realista_espectro.png]]

O mesmo cenário com o receptor original: o quadro se perde.
![[sim_realista_professor_bits.png]]

### BER × $E_b/N_0$

AWGN com fase aleatória, ganho 0,3, 5 quadros de 2000 bits por ponto. Quando o quadro se perde (SFD não encontrado ou tamanho errado), todos os bits contam como errados.

| $E_b/N_0$ (dB) | 0 | 2 | 4 | 6 | 8 | 10 |
|---|---|---|---|---|---|---|
| BPSK teórica | 7,9e-2 | 3,8e-2 | 1,3e-2 | 2,4e-3 | 1,9e-4 | 3,9e-6 |
| com extras | 1 | 1 | 2,3e-1 (1 quadro perdido) | 2,1e-1 (1 perdido) | **2,8e-3** | **0** (10 000 bits) |
| original | 1 | 1 | 1 | 1 | 1 | 1 |

![[sim_ber.png]]

Leitura dos resultados:
- Com os extras, o enlace funciona sem erros a partir de ~10 dB. A 8 dB, a BER fica ~1 ordem de grandeza acima da teórica, por três motivos: o receptor não tem filtro casado (o TX usa RC inteiro, não raiz de RC), o cedo-tarde tem jitter de ±1 amostra e o Costas tem ruído de fase.
- Abaixo de ~6 dB, o problema principal é perder o quadro inteiro, não errar bits isolados. Isso acontece quando o SFD não é achado ou quando o cedo-tarde escorrega um símbolo.
- O original perde todos os quadros nessa curva porque o ganho do canal é 0,3. Isso confirma a sensibilidade à amplitude.

---

## 2. Gravações acústicas do código-base

São os três WAVs de `modem_acustico/sinal/` (8 kHz, 16 bits, 4 s), gravados pelo professor com o código Octave. Mensagem esperada: "OLA". Os resultados estão em `evidencias/wav_professor/`.

| Arquivo | Com extras | Original | Observação |
|---|---|---|---|
| `sinal_rx.wav` | **"OLA"**, SFD 32/32, 0 erros | **"OLA"**, SFD 32/32 | pico 0,22, SNR na decisão ~5,6 dB |
| `sinal_rx2.wav` | **"OLA"**, SFD 32/32, 0 erros | **"OLA"**, SFD 32/32 | pico 0,20, SNR ~5,1 dB |
| `sinal_rx3.wav` | SFD 14/32, não decodifica | SFD 12/32, não decodifica | sinal fraco e curto (só ~0,5 s acima do ruído), provavelmente captura truncada; também falha com RB de 50 a 1000 e Fp de 1 a 3 kHz |

Isso valida o porte contra dados acústicos reais: o Python decodifica as mesmas gravações que o código-base.
O `rx.m` vem com `RB = 400`, mas os arquivos foram gravados a 100 bit/s. Com 400, nenhum deles decodifica.

![[wav_professor_sinal_rx_correlacao_sfd.png]]
![[wav_professor_sinal_rx_constelacao.png]]

---

## 3. Transmissão acústica

> [!todo] A preencher depois da demonstração
> Nenhum resultado acústico da equipe foi registrado ainda. Procedimento em [[Como usar]] e testes T6–T8 em [[Plano de testes]].

### Uma máquina (alto-falante → microfone do mesmo notebook)
| Campo | Valor |
|---|---|
| Data / máquina | |
| Dispositivos (saída / entrada) | |
| Volume, distância, ambiente | |
| Payload | PRBS-7, 64 bits |
| Receptor | com extras / original |
| Pico gravado | |
| SFD (pico, invertido) | |
| Erros / BER | |
| SNR na decisão (dB) | |
| Pasta de evidências | `evidencias/acustico_1maquina_…` |

### Duas máquinas
| Campo | Valor |
|---|---|
| Data / máquinas TX e RX | |
| Distância | |
| Payload | |
| Receptor | |
| SFD (pico, invertido) | |
| Erros / BER | |
| SNR na decisão (dB) | |
| Pasta de evidências | `evidencias/acustico_2maquinas_…` |

### Limitações observadas
- (anotar: eco da sala, volume mínimo que funciona, distância máxima, ruído, efeito do `--professor`)
