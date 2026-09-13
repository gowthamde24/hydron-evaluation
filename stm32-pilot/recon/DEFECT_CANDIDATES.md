# DEFECT_CANDIDATES.md — STM32 pilot

All five sited in the real file:
`firmware/libopencm3-examples/examples/stm32/f4/stm32f4-discovery/usart_irq/usart_irq.c`
(and its linker script). Verification tier is stated honestly per defect.

**Update: switched from QEMU to Renode for dynamic verification** (see `PLATFORM.md`
for the full story and `renode/` for the reusable test scripts). This upgraded S5
from static to genuinely dynamic — real pass/fail, captured live. It also produced
a sharper finding for S3 and S4: they're not blocked by a QEMU-specific bug, they're
blocked by something structural to how instruction-set simulators model
peripherals (byte-level, directly-wired — no simulated pin-mux, no simulated bit
timing), confirmed by testing both against Renode's more complete model and getting
the same non-result. See `PLATFORM.md` for the reasoning; the table below reflects
the current, correct status of each.

| id | class | file:line | current | proposed change | predicted symptom | verification (stated honestly) |
|---|---|---|---|---|---|---|
| S1 | L0 — loud (compile error) | `usart_irq.c:25` | `#include <libopencm3/cm3/nvic.h>` | Delete this line | `make` fails: `nvic_enable_irq` (line 40) and `NVIC_USART2_IRQ` (line 40) undeclared — genuine compiler error, not a link error | **Dynamic, fully real.** `make OPENCM3_DIR=<path>` — actual compiler output, reproducible by anyone with the toolchain installed. |
| S2 | L1 — "doesn't fit" (linker memory region overflow) | `../stm32f4-discovery.ld:26` | `rom (rx) : ORIGIN = 0x08000000, LENGTH = 1024K` | Change to `LENGTH = 4K` | Link fails: `region 'rom' overflowed by N bytes` — a genuine embedded "doesn't fit" failure, not an analogy | **Dynamic, fully real.** Same `make` command — real linker output. This is the actual failure class the original recon template meant by L1 — a literal, verifiable memory-region overflow, not a stretched analogy. |
| S3 | L2 — semi-loud (garbage on wire) | `usart_irq.c:54` | `usart_set_baudrate(USART2, 115200);` | Change to `9600` | On real hardware: the far end (whatever's listening at 115200) reads bit-misaligned garbage, because `USARTDIV` is computed against the wrong target baud while the physical bit period doesn't change on the listening side. No firmware-side error — `usart_enable(USART2)` at line 65 still succeeds. | **Static, and now confirmed structurally unfixable by switching tools.** Tested live against Renode's UART model (`renode/usart_irq_test.resc`): the echo still worked correctly even with the mismatch seeded, because Renode's UART bridge operates at the byte level, not the bit-timed electrical level — there's no independently-clocked second device to desynchronize against in simulation. Verifiable statically: the source diff, and the RM0090 §26.3.4 formula (p.755) applied to the reset-default HSI clock, confirming the resulting `USARTDIV`/`BRR` genuinely differs from the 115200 case. |
| S4 | L3 — silent #1 (wrong AF, pins not routed) | `usart_irq.c:50-51` | `gpio_set_af(GPIOA, GPIO_AF7, GPIO2); gpio_set_af(GPIOA, GPIO_AF7, GPIO3);` | Change `GPIO_AF7` to `GPIO_AF6` on both lines | Every USART2 register (baud, enable, interrupt) is still configured correctly — `usart_enable()` still "succeeds" — but PA2/PA3 are no longer electrically routed to the USART2 peripheral, so no byte ever physically reaches or leaves it. Total silent failure: nothing errors, nothing crashes, no data ever moves. | **Static, and now confirmed structurally unfixable by switching tools.** Tested live against Renode: echo still worked with `GPIO_AF6` seeded, because Renode's `.repl` platform description wires `sysbus.usart2` directly to its backend — the same wiring a correct or incorrect `GPIO_AF` value in firmware can't touch, since no pin-mux layer is simulated between GPIO and the peripheral. Verifiable statically: RM0090's AFR mechanism (§7.3.11, p.195) plus the STM32F407 **datasheet**'s AF table (not RM0090 itself — see `ground_truth.md` G3) for the specific AF7=USART2 fact. |
| S5 | L3 — silent #2 (NVIC masked, ISR never fires) | `usart_irq.c:40` | `nvic_enable_irq(NVIC_USART2_IRQ);` | Delete this line | The USART2 peripheral itself still sets its internal RXNE status flag correctly on byte receipt (visible if you inspect `USART_SR` directly), but the NVIC (the interrupt controller) never forwards that event to the CPU, so `usart2_isr()` (line 87) never runs. No LED toggle, no echo, no error — the peripheral did its job and the software simply never finds out. | **Dynamic, fully real — the one runtime defect this pilot can prove live.** Tested against Renode: baseline sends `X`, gets `X` back; with this defect seeded, sends `X`, **gets nothing, confirmed by a real timeout** (`renode/echo_test.py`). NVIC/interrupt-controller behavior is core-level, not pin-mux or bit-timing, so it's exactly the layer these simulators model correctly. |

## Honest note on S3-S5's verification tiers

S5 is now fully dynamic — a real, reproducible pass/fail difference, not an
inference. S3 and S4 remain static, but for a better-understood, more defensible
reason than "the tool didn't cooperate": they sit below the abstraction layer that
mainstream instruction-set/peripheral simulators model at all, confirmed by testing
the same seeded defects against two independent tools (QEMU, then Renode) and
getting the same structural non-result both times. That's a stronger claim than "we
couldn't get QEMU working" — it's "this class of defect needs real hardware or a
bit-accurate simulation, and here's the empirical evidence for why." When judging
Hydron's debug-prompt responses for S3 and S4, you're still checking "did it
correctly reason about the mechanism" rather than "did it make the physical symptom
go away" — say so explicitly if you write this up.
