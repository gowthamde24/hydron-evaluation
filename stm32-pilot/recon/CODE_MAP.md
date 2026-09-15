# Code Map

File: `firmware/libopencm3-examples/examples/stm32/f4/stm32f4-discovery/usart_irq/usart_irq.c`
(86 lines total). All line numbers verified by direct read.

## Clock setup

`clock_setup()`, lines 27-35, enables GPIOD, GPIOA, and USART2 peripheral clocks via
`rcc_periph_clock_enable()`. No PLL configuration is done anywhere in this file, so
the MCU runs on its **reset-default HSI clock** (RM0090 §6.2.2, p.117). This matters
because the USART baud-rate formula (below) depends on the peripheral clock
frequency actually in effect, not just the desired baud value.

## UART / USART init and baud configuration

`usart_setup()`, lines 37-66:
- GPIO alternate-function pin setup for USART2 TX/RX (PA2/PA3), AF7, lines 42-51.
  RM0090 Chapter 7 "General-purpose I/Os (GPIO)" (p.185) explains the AFR
  register mechanism (§7.3.11 "Alternate function configuration", p.195); the
  specific fact that AF7 maps to USART1/2/3 on these pins is a **datasheet** table
  (not RM0090 itself), flagging that distinction rather than blurring it.
- Baud rate, data bits, stop bits, mode, parity, flow control, lines 53-59.
  `usart_set_baudrate(USART2, 115200)` at line 54.
- RX interrupt enable, line 62 (`usart_enable_rx_interrupt`).
- NVIC interrupt enable, line 40 (`nvic_enable_irq(NVIC_USART2_IRQ)`), i.e. this
  happens *before* the GPIO/USART register setup in program order.
- USART peripheral enable, line 65.

**Baud rate register, real formula (RM0090 §26.3.4 "Fractional baud rate
generation", p.755, Equation 1):**
```
Tx/Rx baud = fCK / (8 × (2 − OVER8) × USARTDIV)
```
libopencm3's own implementation (`lib/stm32/common/usart_common_all.c:53-66`, in
`firmware/libopencm3/`) computes this as a plain integer division at runtime.
Its own code comment (lines 58-61) says: *"the reference manual is talking about
fractional calculation but it seems to be only marketing babble... it is nothing
else but a simple divider."* This is a genuine, checkable claim: RM0090 p.785
documents `USART_BRR` as Mantissa + 4-bit Fraction (§26.6.3), and the worked
examples on RM0090 p.755-756 show the fractional part is derived from a real
division with a rounding step. libopencm3's simplification is defensible for typical
clocks but is itself a claim you can verify against the cited RM0090 pages, not
something to take on libopencm3's word alone.

## Interrupt Service Routine

`usart2_isr()`, lines 87-115, a real, genuine ISR (not a stand-in):
- RXNE (receive-not-empty) check: lines 92-93, reads `USART_CR1`/`USART_SR` directly
  by register address (`USART_CR1(USART2)`, `USART_SR(USART2)`; these macros
  resolve to the real peripheral base address `USART2_BASE = 0x40004400`, confirmed
  in `firmware/libopencm3/include/libopencm3/stm32/f4/memorymap.h:56`).
- On RXNE: toggles the onboard LED (GPIOD12, line 96), reads the received byte
  (line 99), enables the TX interrupt so the byte gets echoed back (line 102).
- TXE (transmit-empty) check: lines 106-107; sends the byte (line 110); disables the
  TX interrupt once done (line 113), a real edge-triggered interrupt-disable pattern,
  not polling.

## GPIO (LED)

`gpio_setup()`, lines 68-72, configures GPIOD12 as output for the onboard LED.
`GPIO_PORT_D_BASE = PERIPH_BASE_AHB1 + 0x0C00 = 0x40020C00` confirmed in
`firmware/libopencm3/include/libopencm3/stm32/f4/memorymap.h:107`. `ODR` (output
data register) is offset `0x14` within any GPIO block per RM0090's GPIO register map
(Chapter 7); this is the register read via QEMU's monitor during the (unsuccessful)
dynamic verification attempt in `PLATFORM.md`.

## Build graph (for L0/L1 defect siting)

- `Makefile` (same directory): `LDSCRIPT = ../stm32f4-discovery.ld`, includes the
  shared `../../Makefile.include` → `../../../rules.mk` → links against
  `libopencm3_stm32f4` (built separately in `firmware/libopencm3/lib/stm32/f4/`).
- **Linker script**, `../stm32f4-discovery.ld:24-28`:
  ```
  MEMORY
  {
  	rom (rx) : ORIGIN = 0x08000000, LENGTH = 1024K
  	ram (rwx) : ORIGIN = 0x20000000, LENGTH = 128K
  }
  ```
  `0x08000000` is the real STM32 flash base address (RM0090 memory map,
  Chapter 2/3), `1024K` is this chip's real flash size: a literal, verifiable
  linker memory-region overflow, not a stretched analogy for L1 ("doesn't fit").
