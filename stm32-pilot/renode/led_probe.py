#!/usr/bin/env python3
"""Polls the running Renode instance's monitor (TCP port 4567) for GPIOD's
ODR register (0x40020C14, bit 12 = PD12, the on-board LED) over several
samples, and reports whether the LED is genuinely toggling or stuck.

Usage:
    1. renode --disable-gui -P 4567 miniblink_test.resc &
    2. sleep 3
    3. python3 led_probe.py

Output: each raw sample, then a verdict (TOGGLING or STUCK).
"""
import socket
import sys
import time

GPIOD_ODR = 0x40020C14
LED_BIT = 1 << 12


def read_odr(sock, wait=0.25):
    sock.sendall(f"sysbus ReadDoubleWord {hex(GPIOD_ODR)}\n".encode())
    time.sleep(wait)
    try:
        data = sock.recv(65536)
    except socket.timeout:
        return None
    # Response looks like: b'sysbus ReadDoubleWord 0x...\n\r0x00001000\r\r\n...'
    text = data.decode(errors="replace")
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("0x") and len(line) == 10:
            try:
                return int(line, 16)
            except ValueError:
                continue
    return None


def main(samples=16, interval=0.3, port=4567):
    s = socket.create_connection(("localhost", port), timeout=5)
    s.settimeout(5)
    time.sleep(0.5)
    try:
        s.recv(65536)  # drain the connection banner
    except socket.timeout:
        pass

    values = []
    for i in range(samples):
        v = read_odr(s)
        values.append(v)
        print(f"sample {i:2d}: ODR={'0x%08x' % v if v is not None else 'READ FAILED'}"
              f"  LED bit={'?' if v is None else (1 if (v & LED_BIT) else 0)}")
        time.sleep(interval)
    s.close()

    led_states = {1 if (v & LED_BIT) else 0 for v in values if v is not None}
    if None in values and len(led_states) == 0:
        print("VERDICT: ALL READS FAILED - could not observe GPIOD ODR at all.")
        return 2
    if led_states == {0, 1}:
        print("VERDICT: TOGGLING - LED bit (PD12) observed both set and clear across samples.")
        return 0
    elif led_states == {0}:
        print("VERDICT: STUCK LOW - LED bit (PD12) never observed set across samples.")
        return 1
    elif led_states == {1}:
        print("VERDICT: STUCK HIGH - LED bit (PD12) never observed clear across samples.")
        return 1
    else:
        print(f"VERDICT: UNEXPECTED - observed states {led_states}")
        return 3


if __name__ == "__main__":
    samples = int(sys.argv[1]) if len(sys.argv) > 1 else 16
    interval = float(sys.argv[2]) if len(sys.argv) > 2 else 0.3
    rc = main(samples, interval)
    sys.exit(rc)
