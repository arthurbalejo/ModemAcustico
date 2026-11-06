---
tags: [modem-acustico, marco2, indice]
---
# Modem acústico: enlace básico (Marco 2)

UFSM00050 Comunicação de Dados, turma 10_312, 2026/2.
Equipe: Arthur Balejo (enlace básico), Renato Ramos (CRC/Hamming), Claus Braccini (TDM).

**Marco 2 (06/11/2026):** demonstração do enlace básico e plano de testes.

## Notas
- [[Arquitetura]]: visão geral, quadro, interfaces entre as camadas da equipe
- [[Transmissor]]: porte do `transmissor.m`
- [[Receptor]]: porte do `receptor_2.m` e os extras
- [[Como usar]]: instalação, simulação, uma máquina, duas máquinas, WAV
- [[Resultados]]: simulação, gravações do código-base e transmissão acústica (separados)
- [[Plano de testes]]: entrada, procedimento, resultado esperado e verificação
- [[Próximos passos]]: CRC/Hamming, TDM, integração

## Parâmetros do enlace (Marco 1)
| Parâmetro | Valor |
|---|---|
| Modulação | BPSK (polar ±1 × portadora) |
| Taxa de bits $R_b$ | 100 bit/s (80 amostras/símbolo) |
| Portadora $F_p$ | 2000 Hz |
| Amostragem $F_a$ | 8000 Hz |
| Formatação de pulso | cosseno levantado, $r = 0{,}5$, atraso 3 símbolos (481 coeficientes) |
| Quadro | preâmbulo (40 bits) + SFD (32 bits) + tamanho (8 bits) + payload + preâmbulo |
| Sincronização | laço de Costas (portadora), cedo-tarde (símbolo), correlação com o SFD (quadro) |

## Pendências
- [ ] Rodar a demonstração acústica (1 máquina e 2 máquinas) e preencher [[Resultados#Transmissão acústica]]
- [ ] **Confirmar com o professor que Python é aceito**: a especificação pede código em MATLAB/Octave e a proposta do Marco 1 pediu essa confirmação. Resolver antes de 06/11.
