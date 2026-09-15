#!/usr/bin/env python3
"""Sends one byte to the running Renode instance's UART bridge (port 3456)
and reports what came back, or that nothing did. Dynamically verifies
usart_irq's echo behavior against each seeded defect.

Usage:
    1. renode --disable-gui -P 4567 usart_irq_test.resc &
    2. sleep 3
    3. python3 echo_test.py

Baseline: SENT b'X' -> ECHOED CORRECTLY b'X'. With S5 (masked NVIC interrupt)
seeded: NO RESPONSE. S3/S4 both still echo correctly here; see PLATFORM.md
for why byte-level socket bridges can't distinguish those two.
"""
import socket


def test_echo(byte=b'X', timeout=3):
    """Send one byte to the Renode UART bridge, return what comes back (or None on timeout)."""
    s = socket.create_connection(('localhost', 3456), timeout=timeout)
    s.sendall(byte)
    s.settimeout(timeout)
    try:
        data = s.recv(16)
        return data
    except socket.timeout:
        return None
    finally:
        s.close()


if __name__ == "__main__":
    sent = b'X'
    result = test_echo(sent)
    if result is None:
        print(f"SENT {sent!r} -> NO RESPONSE (timeout)")
    elif result == sent:
        print(f"SENT {sent!r} -> ECHOED CORRECTLY {result!r}")
    else:
        print(f"SENT {sent!r} -> GOT DIFFERENT BYTES {result!r} (hex: {result.hex()})")
