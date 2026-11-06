---
tags: [modem-acustico, planejamento]
---
# Próximos passos

Voltar: [[00 - Índice]]

## Antes de 06/11 (Marco 2)
- [x] Python autorizado pelo professor (06/11).
- [x] T7 (uma máquina) e T8 (celular → notebook, 30 cm) feitos em 06/11; ver [[Resultados]].
- [ ] Testar volume e distância e anotar as limitações.
- [ ] Escolher as figuras para o PDF do marco: bits enviados × recebidos, correlação do SFD, olho, constelação e espectro (uma execução acústica + simulação realista).

## Renato: CRC-8 e Hamming (7,4), até 13/11
- Criar `modem_py/fec.py` (ou `erros.py`) com `crc8(bits)`, `hamming74_encode(bits)` e `hamming74_decode(bits)`. Todos trabalham só com arrays de bits 0/1 (`numpy.uint8`).
- A injeção controlada de erros pode usar `modem_py.channel.flip_bits(bits, posicoes)`.
- Não é preciso mexer em `transmitter.py` nem em `receiver.py`.

## Claus: TDM, até 13/11
- Criar `modem_py/tdm.py` com `mux(fluxo_a, fluxo_b) -> bits` e `demux(bits) -> (a, b)`, com o cabeçalho $(n_A, n_B)$ protegido por Hamming.
- O resultado de `mux` vai direto para `transmit_bits`, e a saída de `receive_bits` vai para `demux`.
- Lembrar que `receive_bits` devolve o payload completado até múltiplo de 8. O cabeçalho TDM resolve isso.
- Limite de 255 bytes por quadro (campo LEN).

## Integração (27/11)
- Script `modem_py/sistema.py`: fluxos → CRC → Hamming → MUX → `transmit_bits` / `receive_bits` → DEMUX → Hamming → CRC.
- Reaproveitar `evidence.make_evidence` e acrescentar um relatório por fluxo.

## Melhorias possíveis no enlace (opcionais)
- Filtro casado: raiz de RC no TX e no RX. Ganharia ~1 dB, mas foge do código-base.
- Cedo-tarde com média em vários símbolos, para reduzir o jitter em SNR baixa.
- Repetição do quadro para aumentar a chance de captura em duas máquinas (`tx --repetir`).
