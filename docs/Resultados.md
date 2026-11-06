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

### Uma máquina (alto-falante → microfone do mesmo notebook)
| Campo | Valor |
|---|---|
| Data / máquina | 06/11/2026, 17h55 · Lenovo ThinkPad E14 Gen 3, Fedora, PipeWire |
| Dispositivos (saída / entrada) | alto-falante e microfone internos (Ryzen HD Audio, ALC257) |
| Volume, distância, ambiente | reprodução 70%, captura 100%; distância do próprio notebook; residência no centro, perto de rua movimentada, janela sem isolamento (ruído de tráfego) |
| Payload | PRBS-7, 64 bits |
| Comando | `python -m modem_py.acustico --prbs 64` (e `--professor`) |

| Execução | Pasta | Receptor | Pico gravado | SFD | Invertido | Erros | SNR (dB) |
|---|---|---|---|---|---|---|---|
| 1 | `acustico_1maquina_20261106_175455` | extras | 1,45 | −32 | sim | **0/64** | 20,4 |
| 2 | `acustico_1maquina_20261106_175501` | extras | 1,42 | +32 | não | **0/64** | 21,2 |
| 3 | `acustico_1maquina_20261106_175507` | extras | 1,45 | −32 | sim | **0/64** | 15,4 |
| 4 | `acustico_1maquina_20261106_175512` | original | 1,47 | −28 (abaixo de 28,8) | sim | 4/64 (posições 11, 14, 32, 34) | 3,7 |
| 5 | `acustico_1maquina_20261106_175519` | original | 1,42 | +22 (abaixo de 28,8) | não | 10/64 (LEN lido como 9) | 3,2 |

Com os extras, as 3 execuções saíram sem erros. Em duas, o Costas travou em 180° e a correlação com o SFD corrigiu a polaridade. O receptor original não atingiu o limiar do SFD em nenhuma das duas execuções.

![[acustico_bits_enviados_recebidos.png]]
![[acustico_correlacao_sfd.png]]
![[acustico_constelacao.png]]

Receptor original (execução 5):
![[acustico_professor_bits.png]]

### Dois aparelhos (celular → notebook)
| Campo | Valor |
|---|---|
| Data | 06/11/2026, 18h15 a 19h03 |
| TX | Samsung Galaxy S20 FE 5G: `sinal_tx.wav` (gerado por `tx --wav`) servido pela rede local e tocado no navegador |
| RX | ThinkPad E14 Gen 3, microfone interno, captura em 50%: `rx --gravar 20 --nivel 0 --esperado-prbs 64 --evidencias evidencias` |
| Configuração final | 30 cm, 100 bit/s, Dolby Atmos desligado, volume do celular ~50% |
| Ambiente | o mesmo do teste em uma máquina (ruído de tráfego da rua) |

`--nivel 0` porque o ruído de rua (abaixo de 300 Hz) já passava do `NS_min`.

| Execução | Pasta `acustico_2aparelhos_30cm_vol50_…` | SFD | Invertido | Erros | SNR (dB) |
|---|---|---|---|---|---|
| A | `20261106_185920` | 28 (abaixo de 28,8) | não | 1/64 (posição 13) | 3,8 |
| B | `20261106_190030` | −32 | sim | **0/64** | 7,0 |
| C | `20261106_190119` | 22 | não | 29/64 (quadro perdido) | — |
| D | `20261106_190215` | +32 | não | **0/64** | 8,2 |
| E | `20261106_190256` | +32 | não | **0/64** | 8,3 |

Resultado: 3 de 5 sem erros e 1 com um único erro.

![[acustico2_bits_enviados_recebidos.png]]
![[acustico2_correlacao_sfd.png]]
![[acustico2_constelacao.png]]

Tentativas anteriores, todas sem sincronização do quadro:

| Pasta | Condição | Resultado |
|---|---|---|
| `acustico_2aparelhos_1m_20261106_181523` | 1 m, 100 bit/s | **inválida**: a gravação terminou antes de o celular baixar o arquivo |
| `acustico_2aparelhos_30cm_20261106_181647` | volume máximo, Dolby ligado | SFD 20, 30/64 |
| `acustico_2aparelhos_30cm_20261106_184808` | Dolby desligado, volume ~80% | SFD 24, 18/64 |
| `acustico_2aparelhos_30cm_50bps_20261106_184926` | celular tocou o arquivo de 100 bit/s, RX em 50 | **inválida** |
| `acustico_2aparelhos_30cm_50bps_20261106_185130` | 50 bit/s, volume ~80% | SFD −16, 33/64 |
| `acustico_2aparelhos_30cm_vol50_20261106_185631` | celular tocou o arquivo de 50 bit/s, RX em 100 | **inválida** (redecodificada a 50 em `…50bps_vol50_20261106_185648`: SFD 22, 35/64) |

Diagnóstico das falhas: SNR alta na banda (até ~360× o ruído) e portadora exatamente em 2000 Hz, mas a fase do canal, estimada com o sinal transmitido conhecido, variava 1–2,5 rad em janelas de 50 ms. A mudança decisiva foi tocar a 100 bit/s com volume moderado e sem efeitos de áudio.

### Limitações observadas
- Poucas repetições (3 + 2 numa máquina, 5 na configuração final entre aparelhos): as taxas de sucesso ainda não têm significado estatístico.
- Entre aparelhos, só funciona a curta distância (30 cm) e é sensível ao processamento de áudio do celular (Dolby Atmos, volume alto). Faltam distâncias maiores, o sentido inverso e dois computadores.
- O pico gravado passou de 1,0 (~1,45), o que indica ganho de captura alto. O AGC compensa, mas o receptor original não.
- Volume mínimo, distância máxima e efeito do ambiente ainda não foram medidos.
- Com fones Bluetooth conectados, o PipeWire usa os fones como saída e entrada padrão, e os dispositivos JACK não aceitam 8 kHz. Foi preciso trocar o padrão (`wpctl set-default`) para o alto-falante e o microfone internos durante o teste.
