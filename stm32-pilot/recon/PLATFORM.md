# PLATFORM.md — STM32 pilot (real hardware target, real public reference manual)

## Why this target

An initial target for this evaluation was abandoned after recon showed no physical
hardware and no public manual for its own protocol. Rather than fabricate ground
truth to route around that, this pilot targets hardware where genuine public
documentation exists and a real emulator can run the firmware — so grounding claims
can actually be checked, by you or anyone else, not just asserted.

## Target

- **MCU family:** STM32F405/407/415/417/427/437/429/439 (all one reference manual).
  Specific chip used here: **STM32F407VG** (1024 KB flash, 128 KB RAM), the chip on
  the ST STM32F4-Discovery board — confirmed directly from the linker script comment:
  `libopencm3-examples/examples/stm32/f4/stm32f4-discovery/stm32f4-discovery.ld:21`:
  *"Linker script for ST STM32F4DISCOVERY (STM32F407VG, 1024K flash, 128K RAM)."*
- **Firmware source:** [libopencm3](https://github.com/libopencm3/libopencm3) (the
  library, real open-source register-level peripheral drivers, LGPL) +
  [libopencm3-examples](https://github.com/libopencm3/libopencm3-examples) (real
  example programs). Both cloned at `stm32-pilot/firmware/`, shallow clone, ~14MB
  total — real upstream projects, not written for this exercise.
- **Example firmware under test:**
  `libopencm3-examples/examples/stm32/f4/stm32f4-discovery/usart_irq/usart_irq.c` —
  an interrupt-driven USART2 echo server (86 lines). Chosen because it has genuine
  UART init, GPIO alternate-function config, NVIC interrupt enable, and a real ISR —
  the closest match to the original recon template's UART/ISR/telemetry categories.
- **Reference manual:** **RM0090**, "STM32F405/415, STM32F407/417, STM32F427/437 and
  STM32F429/439 advanced ARM-based 32-bit MCUs," Doc ID 018909 Rev 4, February 2013,
  STMicroelectronics — the actual, official, public manual, vendored at
  `stm32-pilot/references/RM0090.pdf`, content verified against ST's own document
  header on page 1 of the PDF itself.
- **Emulator:** QEMU 11.1.1 (`qemu-system-arm`), machine `olimex-stm32-h405`
  (STM32F405-based, Cortex-M4) — genuinely boots the compiled firmware and idles
  correctly in the real `while(1) { NOP }` loop from `main()` (confirmed by
  disassembling the live PC via the QEMU monitor — it sits at the real idle-loop
  address, not stuck or faulted).

  **Root cause of the dynamic-verification gap, precisely diagnosed rather than
  left vague:** `info qtree` in the QEMU monitor shows GPIOD on this SoC model is an
  `unimplemented-device` stub — so the LED-toggle check used in an earlier pass of
  this pilot was checking a fake peripheral and would never have shown a real result
  either way, regardless of whether the interrupt fired. The actual USART2
  peripheral **is** real (`stm32f2xx-usart`, correctly wired to its chardev). Testing
  at the register level: sending a byte into the wired serial device makes it
  genuinely arrive at `USART2_DR` (`0x40004404` reads back `0x58`, the ASCII code
  for the byte sent) — but `USART2_SR`'s RXNE bit (`0x40004400`, bit 5) never sets,
  so neither polling code nor the NVIC interrupt path can ever detect the byte
  arrived. This is confirmed as a **known upstream QEMU limitation**, not a defect
  in this pilot's test setup: a separate long-running fork,
  [`beckus/qemu_stm32`](https://github.com/beckus/qemu_stm32/issues/7), exists
  specifically because of documented RXNE/receive-interrupt bugs in mainline QEMU's
  STM32 UART model.

  **Resolution: switched emulators, and it worked.** [Renode](https://renode.io)
  (Antmicro, MIT-licensed, fully open source, purpose-built for exactly this class
  of peripheral-accurate MCU simulation) ships a real STM32F4-Discovery platform
  (`platforms/boards/stm32f4_discovery.repl`) with a genuine `UART.STM32_UART`
  model — not a stub — its interrupt correctly wired to the NVIC (`-> nvic@38`),
  and real GPIO port models throughout (unlike QEMU's `unimplemented-device` stubs).
  Bridging `sysbus.usart2` to a TCP socket (`renode/usart_irq_test.resc`) and
  sending a byte with `renode/echo_test.py` genuinely worked: the baseline
  firmware echoes the exact byte sent, end to end, through a real
  interrupt-driven path.

  **This produced a sharper, more interesting finding than "QEMU is broken."**
  Testing all three runtime defects (S3 baud, S4 wrong GPIO alternate-function, S5
  masked NVIC interrupt) against Renode's more complete model revealed a structural
  pattern, not a per-tool quirk:
  - **S5 (masked NVIC interrupt) is fully, genuinely dynamically verifiable.**
    Baseline: byte sent, byte echoed. Defect seeded: byte sent, **no response at
    all** — exactly the predicted symptom, confirmed live. This is real proof, not
    static reasoning.
  - **S3 (baud mismatch) and S4 (wrong GPIO alternate-function) are NOT
    dynamically verifiable in either QEMU or Renode — for a specific, structural
    reason, not a bug in either tool.** Both simulators wire a peripheral model
    directly to its backend (a socket, in this setup) as defined in the platform
    description — bypassing the physical GPIO pin-mux layer entirely, and treating
    UART transfer as a byte-level event rather than a bit-timed electrical signal.
    A wrong `GPIO_AF` value therefore never actually disconnects anything in
    simulation (there is no simulated pin-mux to disconnect), and a baud mismatch
    never garbles a byte (there is no independently-clocked receiving device to
    desynchronize against). This is true of instruction-set/peripheral simulators
    generally, not a gap specific to QEMU or Renode — confirmed empirically here by
    testing the *same* defects against *two independent tools* and getting the
    *same* structural non-result both times.

  **Net effect:** L0/L1 (build/link) verification is fully dynamic. L3's NVIC-class
  defect (S5) is now fully dynamic too. L2's baud defect (S3) and L3's pin-mux
  defect (S4) remain static (source + register-level review against RM0090) — not
  because a better emulator would fix it, but because this class of bug lives
  below the abstraction level any mainstream instruction-set simulator models.
  Only real hardware, or a bit-accurate/analog co-simulation, would close that gap.
  See `DEFECT_CANDIDATES.md` for exactly which verification applies to which
  defect, and `renode/` for the reusable test harness itself.
- **Toolchain:** ARM GNU Toolchain 15.2.Rel1, official release.

## Expanded campaign: peripheral-capability recon for 4 new targets

Before adding new firmware targets, checked Renode's actual bundled platform
files (not assumed) — the same discipline that produced the S3/S4 finding
above, applied up front this time instead of discovered mid-pilot.

- **GPIO output is a real model, not a stub.**
  `platforms/boards/stm32f4_discovery.repl` wires GPIOD pin 12 to a genuine
  `Miscellaneous.LED` peripheral (`UserLED: Miscellaneous.LED @ gpioPortD` /
  `12 -> UserLED@0`). Unlike QEMU's `unimplemented-device` GPIOD stub (see
  above), this is dynamically, honestly checkable.
- **GPIO input + the on-board button is a real model.**
  The same file wires `UserButton: Miscellaneous.Button @ gpioPortA` to
  `gpioPortA@0` (pin 0) — a genuine injectable input, not a stub. First
  target in this pilot where a *symptom can be caused* (Press/Release) rather
  than only *output observed*.
- **The `button` example (`examples/.../button/button.c`) is polling, not
  EXTI-interrupt-driven** — confirmed by reading the actual file: it reads
  `gpio_get(GPIOA, GPIO0)` inside the main `while(1)` loop, with no EXTI or
  NVIC configuration anywhere. The original plan assumed an EXTI-based
  button target; corrected after reading the real source rather than forcing
  an EXTI defect onto code that doesn't have EXTI in it. The button target's
  defects (`X1`–`X5`, see `DEFECT_CANDIDATES.md`) are GPIO-polling defects,
  not interrupt-masking ones — X4/X5 are still genuinely dynamic (Press the
  Renode button, check whether the slow-blink behavior responds).
- **The `timer` example (`examples/.../timer/timer.c`) does not route TIM2
  through any GPIO pin or alternate function at all** — confirmed by reading
  the file: `tim2_isr()` reacts to a compare-match event and calls plain
  `gpio_toggle()` on the LED pin; there is no `gpio_set_af()` call or PWM
  hardware-output config anywhere in it. The plan's original "does Renode's
  real per-channel AF routing make a wrong-PWM-pin defect dynamically
  provable, unlike USART's S4?" question **could not be tested on this
  specific example** for that reason — dropped, not silently ignored, and
  replaced with a genuinely-present bug class this file does have: which
  timer *event source* is unmasked in `TIMx_DIER` (see `T4` in
  `DEFECT_CANDIDATES.md`), a real, different silent-failure layer than S5's
  NVIC-level masking (this one is DIER/event-source-level, one layer lower).
- **ADC is not modeled for the F405/407/412/429 series in this Renode
  build.** Confirmed by grep across every `.repl` file in the install — F0,
  G0, L0-family and H7 boards have ADC models; the F4-Discovery's own
  `stm32f4.repl` does not define one. `adc-dac-printf` was dropped as a
  target for this reason — it would only add a second static-only-tier
  peripheral without a new finding.
- **Resolved:** whether Renode's `GPIOPort.STM32_GPIOPort` model gates
  register behavior on the corresponding `RCC_AHB1ENR` clock-enable bit
  (RM0090 §6.3.12, p.145) the way real silicon does. Tested live for both
  the "missing clock-enable" defects (`N5`, `X5` in `DEFECT_CANDIDATES.md`):
  it does not. Both stay static-tier, the same as S3/S4.

## The methodological point this makes

What does Hydron's behavior look like when real, checkable ground truth exists,
versus a target where it doesn't? This pilot answers the first half. The abandoned
initial target answered the second (mostly `UNVERIFIED`, honestly) before the
pivot — that a target can fail this hard on documentation/access grounds is itself
worth remembering when judging how far these results generalize.
