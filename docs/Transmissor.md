---
tags: [modem-acustico, transmissor]
---
# Transmissor

Voltar: [[00 - Índice]] · Ver também: [[Arquitetura]], [[Receptor]]

Arquivos: `modem_py/transmitter.py`, `modem_py/framing.py`, `modem_py/rcos.py`, CLI `modem_py/tx.py`.
Ponto de entrada: `transmit_bits(bits)` (ou `python -m modem_py.tx`).

## Etapas (mesma ordem do `transmissor.m`)

1. **Bits do payload.** Texto vira bytes e depois bits com LSB primeiro, igual a `de2bi(...,8)`. A CLI também aceita uma PRBS-7 (sequência conhecida, a mesma em qualquer máquina) ou bits explícitos.
2. **Enquadramento.** `PRE | SFD | LEN | payload | PRE` (ver [[Arquitetura#Quadro]]). No original, o tamanho entra como primeiro byte da mensagem (`[l msg]`), e aqui é igual.
3. **Codificação polar:** `s = [-1, 1]; y = s(msg+1)`.
4. **Formatação de pulso.** Taxa ajustada `RB_f = Fa/floor(Fa/RB)` = 100 bit/s, ou seja, 80 amostras/símbolo.
   - `rcosine(RB_f, Fa, 'default', 0.5)`: FIR cosseno levantado com atraso 3 símbolos, 481 coeficientes, soma normalizada para 1.
   - `rcosflt(y, RB_f, Fa, 'filter', num)`: um impulso a cada 80 amostras, filtrado. A saída tem `len(y)·80` amostras, então a cauda do filtro é cortada. É por isso que o quadro termina com um segundo preâmbulo.
5. **Modulação BPSK:** `y .* cos(2π·Fp·t)`.
6. **Normalização.** O Octave chama `soundsc`, que escala para [-1, 1] na hora de tocar. Aqui a escala vai para pico = 0,9 (`TxConfig.amplitude`) já na saída de `transmit_bits`, então o mesmo sinal serve para a placa de som e para o WAV.

## Espectro esperado

Com $r = 0{,}5$, a banda ocupada é $F_p \pm (1+r)R_b/2 = 2000 \pm 75$ Hz (1925 a 2075 Hz).

![[sim_realista_espectro.png]]

## Diferenças em relação ao original
- Nenhuma no processamento. Os coeficientes do `rcosine` e o corte do `rcosflt` são os mesmos (verificado em `tests/test_modem.py::test_rcosine_igual_ao_original`).
- `transmissor.m` tem um ramo "MATLAB" com `rcosdesign` e `upfirdn`. Ele não foi portado: foi seguido o ramo Octave, que é o usado nas gravações do professor.
