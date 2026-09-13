# ground_truth.md — STM32 pilot

Most of this is genuinely resolvable — real public documentation exists for this
chip. Filled in from actual sources, cited below;
nothing here came from Claude's or Hydron's general knowledge.

| id | what | file:line | current value in repo | correct value / status | source | verified how |
|---|---|---|---|---|---|---|
| G1 | USART baud rate formula | `usart_irq.c:54` (`usart_set_baudrate(USART2, 115200)`) | libopencm3 computes `BRR = clock/baud` at runtime (`usart_common_all.c:53-66`) | **Resolved.** `Tx/Rx baud = fCK / (8 × (2 − OVER8) × USARTDIV)` | **RM0090** Doc ID 018909 Rev 4, §26.3.4 "Fractional baud rate generation", Equation 1, p.755 | Read directly from the downloaded PDF, 2026-09-13 |
| G2 | STM32F407VG flash/RAM size | `stm32f4-discovery.ld:21,26-27` | `1024K` flash, `128K` RAM | **Resolved.** Matches the linker script's own header comment, a real primary-source artifact from the actual open-source project (not asserted from memory). | `libopencm3-examples` linker script, same file | Read directly, 2026-09-13 |
| G3 | AF7 = USART2 on pins PA2 (TX) / PA3 (RX) | `usart_irq.c:50-51` (`gpio_set_af(GPIOA, GPIO_AF7, ...)`) | Used by working code, consistent with libopencm3's own header definitions | **Resolved.** AF7 column, PA2 row = `USART2_TX`; PA3 row = `USART2_RX`. | **STM32F405xx/STM32F407xx Datasheet**, DocID022152 Rev 8 (STMicroelectronics, Sept 2016), **Table 9 "Alternate function mapping," p.62**. Vendored at `references/DS_STM32F405-407.pdf`. | Read directly, 2026-09-13 |
| G4 | STM32 flash base address `0x08000000` | `stm32f4-discovery.ld:26` | `ORIGIN = 0x08000000` | **Resolved.** RM0090's own memory map table lists `0x0800 0000 - 0x080F FFFF` as "Flash memory" — exact match. | **RM0090**, memory map table, **p.57** | Read directly, 2026-09-13 |
| G5 | Reset-default clock source and its exact frequency (relevant to G1's baud math) | not explicit in `usart_irq.c` — no PLL setup is called anywhere in the file | HSI (High Speed Internal RC oscillator) | **Resolved, including the exact figure.** "The HSI clock signal is generated from an internal 16 MHz RC oscillator." Since `clock_setup()` (`usart_irq.c:27-35`) never touches `RCC_CFGR` or calls a PLL setup routine, the chip stays on this default — so the value that actually goes into G1's `fCK` is 16 MHz (±1% factory-calibrated, per the same section). | **RM0090** §6.2.2 "HSI clock", **p.117** | Read directly, 2026-09-13 |

## What this worksheet demonstrates

**5 of 5 rows fully resolved with real, primary-source citations** — no flagged
gaps remaining. That's the direct, visible effect of picking a target with public
documentation: every hardware fact this evaluation relies on can be checked by
anyone, against a named document and page number, not asserted from an AI's own
knowledge.
