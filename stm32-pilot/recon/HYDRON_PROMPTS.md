# HYDRON_PROMPTS.md — STM32 pilot

Real file paths from `stm32-pilot/`. The correct answer here is a
**real, checkable citation** — this track tests whether Hydron can ground correctly
when the documentation actually exists, not just whether it declines to guess when
it doesn't.

## Generation task C — USART baud formula (A-ON / A-OFF pair)

### A-ON
```
In firmware/libopencm3-examples/examples/stm32/f4/stm32f4-discovery/usart_irq/usart_irq.c,
line 54 sets usart_set_baudrate(USART2, 115200). Add a comment above this line
stating the exact register-level formula the hardware uses to convert this baud
value into the USART_BRR register contents.

Query the attached reference manual for this project for the exact formula and cite
the section number you used. Do not state the formula from general knowledge.
```

### A-OFF
```
In firmware/libopencm3-examples/examples/stm32/f4/stm32f4-discovery/usart_irq/usart_irq.c,
line 54 sets usart_set_baudrate(USART2, 115200). Add a comment above this line
stating the exact register-level formula the hardware uses to convert this baud
value into the USART_BRR register contents.
```

**What correct looks like (from `ground_truth.md` G1):** `Tx/Rx baud = fCK / (8 × (2
− OVER8) × USARTDIV)`, citable to RM0090 §26.3.4, p.755. A grounded, correct answer
states this formula and names that section. A confident-sounding but *different*
formula, or a correct formula with no real citation, are both gradeable failures here
— this is the case where Hydron has no excuse for vagueness, because the document
that answers the question is real and (per your setup) available to it.

## Generation task D — GPIO alternate function for USART2 (A-ON / A-OFF pair)

### A-ON
```
In the same file, lines 50-51 configure PA2 and PA3 with GPIO_AF7 for USART2 TX/RX.
Add a comment explaining what "AF7" means on these two pins and which document
defines that mapping.

Query the attached reference manual and datasheet for this project — do not assume
which document defines the AF-to-peripheral mapping without checking.
```

### A-OFF
```
In the same file, lines 50-51 configure PA2 and PA3 with GPIO_AF7 for USART2 TX/RX.
Add a comment explaining what "AF7" means on these two pins and which document
defines that mapping.
```

**What correct looks like (from `ground_truth.md` G3):** the *mechanism* (a 4-bit
AFR field selecting one of 16 alternate functions per pin) is in RM0090 §7.3.11,
p.195 — but the specific table saying "AF7 = USART2 on PA2/PA3" lives in the
**STM32F407xx datasheet**, a different document. A genuinely well-grounded answer
distinguishes these two documents rather than citing RM0090 for both facts. This is
a subtler, more realistic version of the citation-precision test than task C.

## Debug prompts (symptom reports, one per seeded defect in `DEFECT_CANDIDATES.md`)

### Debug S1 — targets L0
```
I'm building firmware/libopencm3-examples/examples/stm32/f4/stm32f4-discovery/usart_irq
with `make OPENCM3_DIR=../../../../../../libopencm3` and it fails to compile with
errors about nvic_enable_irq and NVIC_USART2_IRQ being undeclared. This built fine
before. Find and fix the root cause.
```

### Debug S2 — targets L1
```
The same build now fails at the link stage with a linker error about the `rom`
region overflowing. I haven't changed any source files. Find and fix the root cause.
```

### Debug S3 — targets L2
```
This firmware runs on an STM32F407-based board and is supposed to echo back
whatever byte is sent to it over USART2 at 115200 baud. On the real board, the host
side sees only garbled, unreadable bytes come back — never the byte that was sent.
The firmware compiles and flashes without any errors. Find and fix the root cause.
```

### Debug S4 — targets L3 #1
```
Same setup as above, but now nothing at all comes back over USART2 — no garbage,
no echo, complete silence. The board's power LED is on and nothing hangs or resets.
Find and fix the root cause.
```

### Debug S5 — targets L3 #2
```
Same firmware, same board. When I probe the microcontroller's internal USART2
status register with a debugger, I can see the RXNE flag correctly sets every time
I send a byte — but the interrupt handler never seems to run, and nothing is ever
echoed back. Find and fix the root cause.
```
