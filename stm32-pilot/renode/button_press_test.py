#!/usr/bin/env python3
"""Dynamically verifies button.c's "hold the button, LED blinks slower" behavior
in Renode: counts LED toggles over a fixed sim-time window with the on-board
button released, then held, and reports the ratio.

Usage:
    python3 button_press_test.py <path-to-button.elf> [--port PORT] [--seconds N]

Baseline firmware: HELD toggles at roughly half the RELEASED rate (the code's
extra delay loop when held). X4 (wrong GPIO pin polled) and X5 (missing clock
enable) both produce equal RELEASED/HELD counts; see DEFECT_CANDIDATES.md.
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
