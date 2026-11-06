---
tags: [modem-acustico, receptor]
---
# Receptor

Voltar: [[00 - Índice]] · Ver também: [[Arquitetura]], [[Transmissor]]

Arquivos: `modem_py/receiver.py`, `modem_py/framing.py`, CLI `modem_py/rx.py`.
Ponto de entrada: `receive_bits(audio)` (ou `python -m modem_py.rx`).

O porte segue o `receptor_2.m`, a versão mais completa do código-base (`receptor_0` não tem Costas nem cedo-tarde, e `receptor_1` não tem cedo-tarde).

## Etapas

1. **Captura** (`rx.m`): grava blocos de `t_captura` segundos até o pico passar de `NS_min = 0,1`, e salva o WAV. Em Python: `audio.record_until_signal`, `--gravar S --nivel 0.1`.
2. **Laço de Costas** (sincronização de portadora). Para cada amostra $k$:
   - $z_s = 2y_k \sin(2\pi F_p t_k + \theta_k)$ e $z_c = 2y_k \cos(2\pi F_p t_k + \theta_k)$
   - os dois ramos passam pelo FIR `fir1(64, 0.001)` (`firwin(65, 0.001)`, mesmo projeto com janela de Hamming)
   - $\theta_{k+1} = \theta_k - \mu \cdot \text{lpf}_s \cdot \text{lpf}_c$, com $\mu = 0{,}03$
3. **Demodulação:** $y \cdot \cos(2\pi F_p t + \theta)$.
4. **Sincronização de símbolo cedo-tarde:** começa em `t = ceil(Fa/RB)` e, a cada símbolo, compara $|y(t-d)|$ com $|y(t+d)|$ ($d = 1$, tolerância `err = 0,01`). O instante anda 1 amostra para o lado maior.
5. **Decisão:** `x = y > 0`.
6. **Sincronização de quadro:** correlação de SFD (±1) com os bits (±1). Se o pico ficar abaixo de $0{,}9 \cdot 32$, aparece o aviso "Muitos erros para decodificar os dados". Se o pico for negativo, os bits são invertidos, o que resolve a ambiguidade de 180° do BPSK.
7. **Payload:** lê LEN (8 bits, LSB primeiro) e devolve `8·LEN` bits.

## Extras

O `receptor_2.m` funciona nas gravações do professor (ver [[Resultados#Gravações acústicas do código-base]]), mas a simulação mostrou três fragilidades. Para cada uma foi adicionado um extra em `RxConfig`. Todos podem ser desligados com `RxConfig.professor()` ou `--professor`, que reproduz o original.

| Extra | Problema no original | Evidência |
|---|---|---|
| **Passa-faixa** Butterworth ordem 4, 1500–2500 Hz (está no diagrama da proposta) | ruído fora da banda entra no Costas e na decisão | — |
| **AGC**: normaliza pelo percentil 99,9 de \|y\| | o passo do Costas é $\mu \cdot A^2$ e a tolerância `err = 0,01` do cedo-tarde é absoluta, então tudo depende do volume da gravação | com ganho 0,3 sem ruído o original erra 10 de 64 bits; com os extras, 0 |
| **Passa-baixas** depois do misturador (FIR 161 coeficientes, corte $R_b$ = 100 Hz) | sem ele, o termo em $2F_p$ = 4 kHz fica no sinal amostrado. Com $F_a = 4F_p$, metade das amostras cai perto de zero, e o cedo-tarde compara amostras de "fase" errada | com desvio de 0,5 Hz o original erra 17/64; com os extras, 0 |

Um corte mais largo (300 Hz, 65 coeficientes) foi testado primeiro, mas deixava passar ruído suficiente para o cedo-tarde escorregar um símbolo inteiro (centenas de bits errados num quadro de 800 bits a 6 dB). Com corte em $R_b$ isso some a partir de ~8 dB.

Outra diferença pequena: no original, os índices de amostragem que sobram no fim do laço cedo-tarde ficam valendo 1 e acabam amostrados. Aqui eles são descartados. Isso não muda nada, porque essa parte está depois do quadro.

## Sinais intermediários
`info["diag"]` traz `theta`, `i`, `q`, `sample_index`, `samples`. São eles que alimentam as figuras de [[Resultados]].

![[sim_realista_sincronizacao.png]]
