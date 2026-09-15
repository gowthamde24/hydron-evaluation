#!/usr/bin/env python3
"""Polls the running Renode instance's monitor (TCP port 4568, opened by
`renode --disable-gui -P 4568 timer_led_test.resc`) for GPIOD's ODR register
value repeatedly over a fixed wall-clock window, and counts how many times
bit 12 (the on-board LED pin, PD12) actually transitioned.

Unlike led_probe.py (miniblink's TOGGLING-vs-STUCK check), this test's two
predicted outcomes both toggle -- the whole point of the T4 defect is a rate
change, not a stuck pin. Baseline (correct TIM_DIER_CC1IE) should show many
transitions in a ~20s window (Morse element timings are 100ms-700ms apart -
a full 18-element SOS cycle is ~3.4s of simulated time). The T4 defect
(TIM_DIER_UIE only) should show at most one transition in the same window,
because tim2_isr only ever fires on the ~13.1s counter-overflow event.

GPIOD's base address is 0x40020C00 (platforms/cpus/stm32f4.repl); ODR
(output data register) is at offset 0x14, so GPIOD's ODR lives at
0x40020C14. Bit 12 corresponds to PD12, the pin wired to Renode's UserLED
model in platforms/boards/stm32f4_discovery.repl.

Usage:
    1. renode --disable-gui -P 4568 timer_led_test.resc &
    2. sleep 3   # give the emulator time to boot
    3. python3 timer_led_probe.py [window_seconds] [poll_interval]
"""
import socket
import sys
import time

GPIOD_ODR = 0x40020C14
LED_BIT = 1 << 12


def read_odr(sock, wait=0.08):
    sock.sendall(f"sysbus ReadDoubleWord {hex(GPIOD_ODR)}\n".encode())
    time.sleep(wait)
    try:
        data = sock.recv(65536)
    except socket.timeout:
        return None
    text = data.decode(errors="replace")
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("0x") and len(line) == 10:
            try:
                return int(line, 16)
            except ValueError:
                continue
    return None


def main(window=20.0, interval=0.15, port=4568):
    s = socket.create_connection(("localhost", port), timeout=5)
    s.settimeout(5)
    time.sleep(0.5)
    try:
        s.recv(65536)  # drain the connection banner
    except socket.timeout:
        pass

    start = time.time()
    prev = None
    transitions = 0
    transition_times = []
    samples = 0
    while time.time() - start < window:
        v = read_odr(s)
        samples += 1
        if v is None:
            time.sleep(interval)
            continue
        bit = 1 if (v & LED_BIT) else 0
        if prev is not None and bit != prev:
            transitions += 1
            transition_times.append(round(time.time() - start, 2))
        prev = bit
        time.sleep(interval)
    s.close()

    elapsed = round(time.time() - start, 2)
    print(f"Observed {samples} samples over {elapsed}s wall-clock.")
    print(f"Transitions on PD12: {transitions}")
    print(f"Transition wall-clock timestamps (s): {transition_times}")
    if transitions >= 5:
        print("VERDICT: FAST CADENCE (many transitions) - consistent with correct sub-second Morse timing.")
        return 0
    elif transitions <= 1:
        print("VERDICT: SLOW CADENCE (<=1 transition) - consistent with the ~13.1s T4 defect period.")
        return 1
    else:
        print(f"VERDICT: AMBIGUOUS ({transitions} transitions) - re-run with a longer window.")
        return 2


if __name__ == "__main__":
    window = float(sys.argv[1]) if len(sys.argv) > 1 else 20.0
    interval = float(sys.argv[2]) if len(sys.argv) > 2 else 0.15
    rc = main(window, interval)
    sys.exit(rc)
