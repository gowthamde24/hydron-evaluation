#!/usr/bin/env python3
"""Dynamically verifies button.c's "hold the button, LED blinks slower" behavior
against a real Renode simulation of the STM32F4-Discovery board.

Unlike echo_test.py (which just sends one byte and checks the response, since
the usart_irq target's defects are checkable with a single request/response),
this test needs to measure a *rate*: how many times the LED (a genuine
Miscellaneous.LED model at sysbus.gpioPortD.UserLED, see recon/PLATFORM.md)
toggles over a fixed window of simulated time, once with the on-board button
(a genuine Miscellaneous.Button model at sysbus.gpioPortA.UserButton,
Press()/Release()-injectable, also confirmed non-stub in PLATFORM.md) held,
and once released. It drives Renode's monitor directly over its `-P` TCP port
(plain text protocol: send a command line, read back the echoed command, its
result, and a colored prompt) rather than going through a .resc script for the
whole run, because the run needs interleaved Press/Release + timed sampling
that a static .resc script can't express.

How it fits together:
  1. Launches `renode --disable-gui -P <port> button_test.resc` as a
     subprocess (button_test.resc loads the platform description and the ELF
     given by the $elf variable, then stops — no `start`, this script drives
     execution itself).
  2. Connects to the monitor port and, for each of "released" and "held",
     repeatedly calls `emulation RunFor "0.02"` (20ms of simulated time) and
     samples `sysbus.gpioPortD.UserLED State` between steps, counting
     transitions over a fixed total window (default 3s simulated).
  3. Reports both toggle counts and their ratio.

Usage:
    python3 button_press_test.py <path-to-button.elf> [--port PORT] [--seconds N]

Expected output on correctly-working (baseline) firmware:
    RELEASED: ~34 toggles / 3.0s sim-time
    HELD:     ~17 toggles / 3.0s sim-time   (~2.0x slower - matches the code's
                                              extra 3,000,000-iteration delay
                                              loop added only when held)

Expected output with X4 (gpio_get polls GPIO1 instead of GPIO0, so the real
GPIOA0 button has zero effect) or X5 (GPIOA's peripheral clock never enabled)
seeded: RELEASED and HELD toggle counts equal (or, for X5, whatever Renode's
GPIO model actually does when unclocked - this is the open question
DEFECT_CANDIDATES.md flags; this script's job is to report the real observed
numbers, not assume the answer).
"""
import socket
import subprocess
import sys
import time
import argparse
import os

RENODE_BIN = "renode"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RESC = os.path.join(SCRIPT_DIR, "button_test.resc")


def monitor_cmd(sock, command, wait=0.12):
    sock.sendall((command + "\n").encode())
    time.sleep(wait)
    try:
        return sock.recv(65536).decode(errors="replace")
    except socket.timeout:
        return ""


def get_led_state(sock):
    resp = monitor_cmd(sock, "sysbus.gpioPortD.UserLED State")
    for line in resp.splitlines():
        line = line.strip()
        if line == "True":
            return True
        if line == "False":
            return False
    return None


def count_toggles(sock, seconds, step=0.02):
    steps = int(seconds / step)
    toggles = 0
    prev = get_led_state(sock)
    for _ in range(steps):
        monitor_cmd(sock, 'emulation RunFor "%s"' % step, wait=0.08)
        cur = get_led_state(sock)
        if cur is not None and cur != prev:
            toggles += 1
            prev = cur
    return toggles


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("elf", help="path to button.elf to test")
    ap.add_argument("--port", type=int, default=4610)
    ap.add_argument("--seconds", type=float, default=3.0)
    args = ap.parse_args()

    elf_abs = os.path.abspath(args.elf)
    if not os.path.isfile(elf_abs):
        print("ERROR: elf not found: %s" % elf_abs, file=sys.stderr)
        sys.exit(1)

    # Write a temp .resc with the ELF path baked in directly, matching the
    # pattern used elsewhere in this pilot (e.g. usart_irq_test.resc).
    tmp_resc = "/tmp/button_press_test_%d.resc" % args.port
    with open(RESC) as f:
        resc_body = f.read()
    resc_body = resc_body.replace(
        "$elf?=@/Users/gowthamreddys/Desktop/hydron-evaluation/stm32-pilot/firmware/libopencm3-examples/examples/stm32/f4/stm32f4-discovery/button/button.elf",
        "$elf?=@%s" % elf_abs,
    )
    with open(tmp_resc, "w") as f:
        f.write(resc_body)

    log_path = "/tmp/button_press_test_renode_%d.log" % args.port
    logf = open(log_path, "wb")
    proc = subprocess.Popen(
        [RENODE_BIN, "--disable-gui", "-P", str(args.port), tmp_resc],
        stdout=logf, stderr=subprocess.STDOUT,
    )
    try:
        time.sleep(3)
        sock = socket.create_connection(("localhost", args.port), timeout=10)
        sock.settimeout(10)
        time.sleep(0.5)
        sock.recv(65536)  # discard banner

        released = count_toggles(sock, args.seconds)

        monitor_cmd(sock, "sysbus.gpioPortA.UserButton Press")
        held = count_toggles(sock, args.seconds)

        monitor_cmd(sock, "quit")
        sock.close()

        ratio = (released / held) if held else float("inf")
        print("ELF: %s" % elf_abs)
        print("RELEASED: %d toggles / %.1fs sim-time" % (released, args.seconds))
        print("HELD:     %d toggles / %.1fs sim-time" % (held, args.seconds))
        print("RATIO (released/held): %.2f" % ratio)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        logf.close()


if __name__ == "__main__":
    main()
