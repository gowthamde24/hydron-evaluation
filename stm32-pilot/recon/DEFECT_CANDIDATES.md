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

## Expanded campaign — 4 new targets, 20 new defects

Same taxonomy (L0 loud/compile, L1 loud/link, L2 semi-loud/plausible-wrong,
L3 silent ×2), applied to 4 more real example files so findings are
comparable class-by-class, not just target-by-target. Recon for each file
was done by direct read (see corrected notes in `PLATFORM.md` where the
original plan's assumption about a file didn't match its real content —
`button.c` turned out to be polling, not EXTI; `timer.c` doesn't route
through any GPIO alternate function). New IDs (`N`, `T`, `X`, `U`) avoid
collision with `S1`-`S5` and with `ground_truth.md`'s own `G`-prefixed fact
rows.

### `miniblink` — GPIO output (`examples/.../miniblink/miniblink.c`)

| id | class | file:line | current | proposed change | predicted symptom | verification (stated honestly) |
|---|---|---|---|---|---|---|
| N1 | L0 | `miniblink.c:22` | `#include <libopencm3/stm32/gpio.h>` | Delete this line | `make` fails: `gpio_mode_setup`/`gpio_toggle` undeclared | **Dynamic, fully real** — real compiler output. |
| N2 | L1 | `../stm32f4-discovery.ld:26` | `LENGTH = 1024K` | Change to `LENGTH = 4K` | Link fails: `region 'rom' overflowed` | **Dynamic, fully real** — same shared linker script as S2, same real linker output. |
| N3 | L2 | `miniblink.c:66` | `for (i = 0; i < 1000000; i++)` | Change to `i < 100000` | LED still blinks, but ~10× faster than intended — plausible, not obviously broken | **Static.** Grounded in `ground_truth.md` G5 (HSI 16 MHz default, no PLL setup in this file either) — the loop count is the only timing reference, so the wrong count is a verifiable-by-math wrong value. Whether Renode's simulated time resolves the rate difference precisely enough to call this dynamic is to be determined by the actual run, not assumed. |
| N4 | L3 #1 (wrong routing) | `miniblink.c:37` | `gpio_mode_setup(GPIOD, GPIO_MODE_OUTPUT, GPIO_PUPD_NONE, GPIO12);` | Change `GPIO12` to `GPIO13` (line 65's `gpio_toggle(GPIOD, GPIO12)` stays unchanged) | GPIO12 is never taken out of its reset-default Input mode (`ground_truth.md` G7), so `gpio_toggle`'s ODR write has no external effect — LED never lights, nothing errors | **Dynamic, fully real.** GPIOD12 is wired to a genuine `Miscellaneous.LED` model in Renode (see `PLATFORM.md`), not a stub — checkable live. |
| N5 | L3 #2 (missing enable) | `miniblink.c:30` | `rcc_periph_clock_enable(RCC_GPIOD);` | Delete this line | GPIOD's peripheral clock (RCC_AHB1ENR bit 3, `ground_truth.md` G6) is never enabled | **Open, to be determined by this run.** Whether Renode's GPIO model gates on the RCC clock-enable bit the way real silicon does is flagged as unresolved in `PLATFORM.md` — report the real observed result here once run, don't assume either tier in advance. |

### `timer` — Timer/PWM via NVIC (`examples/.../timer/timer.c`)

| id | class | file:line | current | proposed change | predicted symptom | verification (stated honestly) |
|---|---|---|---|---|---|---|
| T1 | L0 | `timer.c:24` | `#include <libopencm3/stm32/timer.h>` | Delete this line | `make` fails: `timer_set_mode`/`timer_set_prescaler`/etc. undeclared | **Dynamic, fully real.** |
| T2 | L1 | `../stm32f4-discovery.ld:26` | `LENGTH = 1024K` | Change to `LENGTH = 4K` | Link fails: `region 'rom' overflowed` | **Dynamic, fully real.** |
| T3 | L2 | `timer.c:107` | `timer_set_prescaler(TIM2, ((rcc_apb1_frequency * 2) / 5000));` | Change divisor `5000` to `500` | Timer runs ~10× too fast — LED still blinks a pattern, just at the wrong tempo | **Static**, grounded in `ground_truth.md` G8 (APB1→timer ×2 rule, RM0090 p.115) applied to the file's own 168 MHz clock setup. Dynamic timing check via Renode's CNT register possible in principle — confirm empirically rather than assume. |
| T4 | L3 #1 (wrong event source unmasked — a genuinely different mechanism than S5, one register layer lower) | `timer.c:123` | `timer_enable_irq(TIM2, TIM_DIER_CC1IE);` | Change to `timer_enable_irq(TIM2, TIM_DIER_UIE);` | `CC1IF` (`ground_truth.md` G9) still sets in hardware on every real compare match — confirmed by RM0090 §15.4.5 p.465-466, which states CC1IF is "set by hardware when the counter matches the compare value" with no mention of CC1IE gating the flag itself, only the NVIC signal. With only `UIE` unmasked, `tim2_isr` is entered only on the ~13.1 s counter-overflow period (65536 counts @ 5 kHz) instead of the intended sub-second Morse cadence — LED toggles, just at a wildly wrong, very slow rate. Not silent, but a distinct failure shape from S5 (S5: correct event, NVIC never told at all; T4: NVIC told, but about the wrong event). | **Dynamic, plausible.** A real, predicted-in-advance rate difference (sub-second vs. ~13s) should be observable in Renode by timing LED toggles against simulated time — confirm with an actual run rather than asserting the tier here. |
| T5 | L3 #2 (missing enable) | `timer.c:85` | `nvic_enable_irq(NVIC_TIM2_IRQ);` | Delete this line | Same mechanism as S5, different peripheral: TIM2 sets its internal flags correctly, NVIC never forwards any of them, `tim2_isr` never runs at all — LED never toggles, fully silent | **Dynamic, fully real** — same NVIC-masking mechanism already proven dynamically provable for S5; expected to hold here too, confirm with the actual run. |

### `button` — GPIO input, polling (`examples/.../button/button.c`)

Corrected from the original plan's EXTI assumption after reading the real
file — see `PLATFORM.md`. No EXTI or NVIC configuration exists in this
example; it polls `gpio_get()` in the main loop.

| id | class | file:line | current | proposed change | predicted symptom | verification (stated honestly) |
|---|---|---|---|---|---|---|
| X1 | L0 | `button.c:23` | `#include <libopencm3/stm32/gpio.h>` | Delete this line | `make` fails: `gpio_mode_setup`/`gpio_get`/etc. undeclared | **Dynamic, fully real.** |
| X2 | L1 | `../stm32f4-discovery.ld:26` | `LENGTH = 1024K` | Change to `LENGTH = 4K` | Link fails: `region 'rom' overflowed` | **Dynamic, fully real.** |
| X3 | L2 | `button.c:64` | `for (i = 0; i < 3000000; i++)` (slow-blink delay on button press) | Change to `i < 500000` | Button press still visibly slows the blink, just by the wrong amount | **Static**, grounded in the file's own 168 MHz `rcc_clock_setup_pll` call (line 28) — a verifiable-by-math wrong value, same style as N3/T3. |
| X4 | L3 #1 (wrong routing) | `button.c:63` | `if (gpio_get(GPIOA, GPIO0)) {` | Change `GPIO0` to `GPIO1` | The real button (wired to GPIOA0, `PLATFORM.md`) has zero effect on blink rate — software polls a pin nothing is connected to | **Dynamic, fully real.** The on-board button is a genuine `Miscellaneous.Button` model in Renode, injectable via `Press()`/`Release()` — not a stub. |
| X5 | L3 #2 (missing enable) | `button.c:44` | `rcc_periph_clock_enable(RCC_GPIOA);` | Delete this line | GPIOA's peripheral clock (RCC_AHB1ENR bit 0, `ground_truth.md` G6) never enabled — button reads become meaningless | **Open, to be determined by this run** — same unresolved clock-gating question as N5, flagged in `PLATFORM.md`, not assumed either way. |

### `usart` (polling, no NVIC) — (`examples/.../usart/usart.c`)

Same USART2 peripheral as `usart_irq`, deliberately different control flow
(blocking/polling sends, no interrupt, no NVIC at all) — isolates whether
Hydron's behavior changes with interrupt- vs. polling-style code on the same
hardware fact set.

| id | class | file:line | current | proposed change | predicted symptom | verification (stated honestly) |
|---|---|---|---|---|---|---|
| U1 | L0 | `usart.c:23` | `#include <libopencm3/stm32/usart.h>` | Delete this line | `make` fails: `usart_set_baudrate`/etc. undeclared | **Dynamic, fully real.** |
| U2 | L1 | `../stm32f4-discovery.ld:26` | `LENGTH = 1024K` | Change to `LENGTH = 4K` | Link fails: `region 'rom' overflowed` | **Dynamic, fully real.** |
| U3 | L2 | `usart.c:38` | `usart_set_baudrate(USART2, 115200);` | Change to `9600` | Same mechanism as S3 — garbled bytes on real hardware, `usart_enable()` still succeeds | **Static.** Same structural limitation as S3 (`ground_truth.md` G1, G5) — expected, confirm rather than assume. |
| U4 | L3 #1 (wrong AF value) | `usart.c:58` | `gpio_set_af(GPIOA, GPIO_AF7, GPIO2);` | Change `GPIO_AF7` to `GPIO_AF6` | Same mechanism as S4 — peripheral fully configured, pin not electrically routed | **Static.** Same structural limitation as S4 — expected, confirm rather than assume. |
| U5 | L3 #2 (wrong GPIO mode, not AF at all — a different mechanism than U4) | `usart.c:55` | `gpio_mode_setup(GPIOA, GPIO_MODE_AF, GPIO_PUPD_NONE, GPIO2);` | Change `GPIO_MODE_AF` to `GPIO_MODE_OUTPUT` | The pin's `MODER` bits (`ground_truth.md` G7) never select alternate-function mode at all, so the AF value set at line 58 is moot — USART2 registers are all correctly configured and `usart_enable()` succeeds, but PA2 is a plain GPIO output, never routed to the peripheral | **Hypothesized static, confirm empirically.** Likely the same structural limitation as U4/S4 (no simulated pin-mux layer for USART), but this is a genuinely different register-level mechanism (MODER, not AFR) — worth actually checking rather than assuming the same tier applies for the same reason. |

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
