#!/usr/bin/env python3
"""Sends one byte to the running Renode instance's UART bridge (port 3456)
and reports exactly what came back, or that nothing did. Used to dynamically
verify usart_irq's echo behavior against each seeded defect.

How this fits together:
  usart_irq_test.resc (run separately, first) boots the firmware inside
  Renode and bridges the emulated USART2 peripheral to a plain TCP socket
  on port 3456 (see that file's `CreateServerSocketTerminal` line). From the
  outside, that socket behaves exactly like a real serial port: whatever
  byte you write to it is what the firmware's UART receives, and whatever
  the firmware transmits back comes out the other end of the same socket.

  This script is the "outside" - it does nothing Renode-specific itself,
  it's just a minimal TCP client. Anything that can open a TCP socket
  (netcat, a serial terminal via socat, another Python script) could do
  the same test manually; this just automates the send-and-check.

Usage:
    1. renode --disable-gui -P 4567 usart_irq_test.resc &
    2. sleep 3   # give the emulator time to boot and bind the socket
    3. python3 echo_test.py

Expected output on correctly-working firmware:
    SENT b'X' -> ECHOED CORRECTLY b'X'

Expected output with the S5 (masked NVIC interrupt) defect seeded:
    SENT b'X' -> NO RESPONSE (timeout)

This is the ONE seeded defect in this pilot where this test can actually
show a real pass/fail difference - see recon/PLATFORM.md for exactly why
S3 (baud mismatch) and S4 (wrong GPIO alternate function) will both still
show a correct echo here even with the defect seeded (it's a real, structural
limitation of what byte-level socket bridges like this one can simulate, not
a bug in this script).
"""
import socket


def test_echo(byte=b'X', timeout=3):
    """Open a fresh TCP connection to the Renode UART bridge, send exactly
    one byte, and return whatever comes back within `timeout` seconds.

    Returns:
        bytes   - whatever was actually received (may or may not equal `byte`)
        None    - nothing came back before the timeout expired
    """
    s = socket.create_connection(('localhost', 3456), timeout=timeout)
    s.sendall(byte)
    s.settimeout(timeout)
    try:
        # 16 bytes is generous headroom - this firmware only ever echoes
        # back the single byte it received, so anything more than 1 byte
        # coming back would itself be worth noticing.
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
        # Not observed in this pilot, but worth distinguishing from a clean
        # timeout - different bytes coming back would point to a framing or
        # buffering issue rather than "interrupt never fired at all".
        print(f"SENT {sent!r} -> GOT DIFFERENT BYTES {result!r} (hex: {result.hex()})")
