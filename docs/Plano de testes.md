---
tags: [modem-acustico, testes]
---
# Plano de testes

Voltar: [[00 - Índice]] · Resultados: [[Resultados]]

Tipo: **S** = simulação por software, **A** = transmissão acústica. A especificação exige que o relatório mantenha os dois separados.
Os testes automáticos ficam em `tests/test_modem.py` e rodam com `.venv/bin/python -m pytest -q`.

## Enlace básico (Marco 2)

### T1. Filtro e quadro iguais ao código-base (S)
- **Entrada:** `rcosine(100, 8000, 0.5, 3)`; payload "OLA".
- **Procedimento:** `pytest -k "rcosine or quadro or lsb"`.
- **Resultado esperado:** 481 coeficientes simétricos com soma 1 e zeros nos múltiplos de 80 amostras; quadro de 144 bits com PRE nos bits 0–39, SFD nos bits 40–71 e LEN = 3; 'O' = `11110010` (LSB primeiro).
- **Verificação:** os testes passam. O quadro bate com `[PRE SFD de2bi([3 'OLA'],8) PRE]` do `transmissor.m`.

### T2. Laço TX → RX ideal (S)
- **Entrada:** "OLA" e PRBS-7 de 64 bits, sem canal (equivale ao `teste.m`).
- **Procedimento:** `pytest -k loopback_ideal`; `python -m modem_py.simular` (cenário `ideal`).
- **Resultado esperado:** "OLA" recuperado nos dois receptores, 0 erros, SFD 32/32.
- **Verificação:** `evidencias/simulacao/*/ideal/relatorio.json` com `comparacao.equal = true`.

### T3. Canal simulado realista (S)
- **Entrada:** PRBS-7 de 64 bits, com atraso de 0,5 s, ganho 0,3, fase 1 rad, desvio de 0,5 Hz, relógio 100 ppm e $E_b/N_0$ = 12 dB (semente 1).
- **Procedimento:** `pytest -k canal_realista`; cenário `realista` do `simular`.
- **Resultado esperado:** 0 erros com os extras.
- **Verificação:** figura `bits_enviados_recebidos.png` sem marcas vermelhas; pico do SFD ≥ 28,8.

### T4. Ambiguidade de fase de 180° (S)
- **Entrada:** portadora girada π rad.
- **Procedimento:** `pytest -k fase_180`; cenário `fase_180`.
- **Resultado esperado:** pico do SFD negativo (−32), `polaridade_invertida = true`, 0 erros depois da inversão.
- **Verificação:** `relatorio.json` → `quadro.polaridade_invertida`; figura `correlacao_sfd.png` com o pico para baixo.

### T5. Detecção do SFD e limiar (S)
- **Entrada:** quadro com 1 e com 3 bits do SFD invertidos (`flip_bits`); ruído puro sem sinal.
- **Procedimento:** `pytest -k "limiar or sem_sinal"`.
- **Resultado esperado:** com 1 erro, pico 30, quadro aceito. Com 3 erros, pico 26 < 28,8, quadro rejeitado. Com ruído puro, `ok = false`.
- **Verificação:** os testes passam. Isso mostra o limite de 0,9·32 herdado do `receptor_2.m`.

### T6. Gravações acústicas do código-base (A, gravadas pelo professor)
- **Entrada:** `modem_acustico/sinal/sinal_rx*.wav`.
- **Procedimento:** `pytest -k gravacoes`; o `simular` gera `evidencias/wav_professor/`.
- **Resultado esperado:** "OLA" em `sinal_rx.wav` e `sinal_rx2.wav`, nos dois receptores.
- **Verificação:** `evidencias/wav_professor/resumo.json`.

### T7. Acústico em uma máquina (A)
- **Entrada:** PRBS-7 de 64 bits; volume ~70%, sala silenciosa.
- **Procedimento:** `python -m modem_py.acustico --prbs 64`. Repetir 5 vezes e depois mais 5 com `--professor`.
- **Resultado esperado:** 0 erros e SFD ≥ 28,8 na maioria das execuções com os extras.
- **Verificação:** cada pasta `evidencias/acustico_1maquina_*` tem `sinal_rx.wav`, as figuras e `relatorio.json`. Anotar a taxa de sucesso em [[Resultados#Transmissão acústica]].

### T8. Acústico em duas máquinas (A)
- **Entrada:** PRBS-7 de 64 bits e o texto "UFSM COMUNICACAO DE DADOS".
- **Procedimento:** RX: `python -m modem_py.rx --gravar 5 --esperado-prbs 64 --evidencias evidencias`. TX: `python -m modem_py.tx --prbs 64 --tocar`. Repetir a 0,5 m, 1 m e 2 m.
- **Resultado esperado:** 0 erros pelo menos a 0,5 m.
- **Verificação:** `relatorio.json` na pasta `acustico_2maquinas_*`. Para a demonstração, os bits enviados (impressos pelo TX) e os recebidos (impressos pelo RX) aparecem lado a lado na tela.

### T9. Variante via arquivo WAV (A)
- **Entrada:** `sinal_tx.wav` gerado por `tx --wav`.
- **Procedimento:** tocar num celular ou player, gravar com outro aparelho e rodar `rx --wav captura.wav --esperado-prbs 64 --evidencias evidencias --cenario acustico_wav`.
- **Resultado esperado:** igual ao T8. A reamostragem de 44,1/48 kHz para 8 kHz é automática.
- **Verificação:** `relatorio.json` na pasta `acustico_wav_*`.

### T10. BER × Eb/N0 (S)
- **Entrada:** 5 quadros de 2000 bits por ponto, $E_b/N_0$ de 0 a 10 dB.
- **Procedimento:** `python -m modem_py.simular`.
- **Resultado esperado:** curva do receptor com extras chegando à teórica, com 0 erros em 10 dB.
- **Verificação:** `evidencias/simulacao/ber.png` e `ber.json`.

## Próximas etapas (Marcos 3 e 4)

Os testes abaixo estão só planejados. A implementação é de Renato e Claus (ver [[Próximos passos]]).

| Teste | Tipo | Entrada | Procedimento | Resultado esperado | Verificação |
|---|---|---|---|---|---|
| T11 CRC-8 detecta erro | S | 1 byte + CRC-8 ($x^8+x^2+x+1$); inverter 1, 2 e 3 bits | `flip_bits` depois de `crc_encode` | CRC acusa o erro em 100% dos casos com 1 a 2 bits | tabela de casos |
| T12 Hamming corrige 1 erro | S | bloco de 7 bits; 1 erro em cada posição | 7 casos | dados recuperados nos 7 | comparação bit a bit |
| T13 limite do Hamming | S | 2 erros no mesmo bloco | decodifica e passa pelo CRC | Hamming erra a correção, e o CRC detecta | CRC = falha |
| T14 TDM 2 fluxos | S | fluxos A e B de tamanhos diferentes | MUX → `transmit_bits` → `receive_bits` → DEMUX | A' = A e B' = B | `compare_bits` para cada fluxo |
| T15 integrado | A | A e B com CRC + Hamming + TDM | transmissão acústica | os dois fluxos recuperados e o CRC ok | relatório por fluxo |
