#!/usr/bin/env bash
# setup.sh - Reproduces the STM32 pilot's build environment from scratch.
#
# Checks for a working ARM cross-compiler, QEMU, and Renode (see
# recon/PLATFORM.md), clones the firmware repos at pinned commits, builds
# the library, and smoke-tests a build of the firmware under test.
#
# Safe to re-run any time: every step checks current state before acting.

# -u : fail on use of an unset variable (catches typos in variable names)
# -o pipefail : a pipeline's exit status is its last *failing* command, not
#               just the last command - so `cmd | grep x` reports cmd's failure too
set -uo pipefail

# Resolve the directory this script actually lives in, and run from there,
# so it works correctly no matter what directory you invoke it from.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Pinned to the exact commits this pilot's recon docs cite file:line references
# against. Do not change these without re-verifying every line number in
# recon/CODE_MAP.md and recon/DEFECT_CANDIDATES.md - a newer upstream commit
# could silently move the lines those documents point at.
LIBOPENCM3_COMMIT="2da12dc96e0b9e42a3332348dd9b02a0a17981f8"
LIBOPENCM3_EXAMPLES_COMMIT="15637e291b8ca228e35d5f657ed15f3b8958fa0c"

# Small output helpers: green check, red cross, bold section header.
# (\033[...m are ANSI color codes; \033[0m resets back to normal.)
pass() { printf "  \033[32m✓\033[0m %s\n" "$1"; }
fail() { printf "  \033[31m✗\033[0m %s\n" "$1"; }
info() { printf "\033[1m%s\033[0m\n" "$1"; }

FAILED=0   # tracks whether anything failed, checked at the end of each phase

# --- Step 1: cross-compiler ------------------------------------------------
# We don't just check `command -v` (is it on PATH) - we actually try to
# compile a trivial program, because Homebrew's arm-none-eabi-gcc formula
# was found to be on PATH but non-functional (ships without newlib, so
# <stdint.h> and friends don't exist). "Present" and "working" are different
# questions, and only the second one matters.
info "1/5 - checking for a working ARM cross-compiler"
if command -v arm-none-eabi-gcc >/dev/null 2>&1; then
  if echo 'int main(void){return 0;}' | arm-none-eabi-gcc -x c - -o /tmp/_toolchain_check.o -c 2>/tmp/_toolchain_check.log; then
    pass "arm-none-eabi-gcc found and can compile ($(arm-none-eabi-gcc --version | head -1))"
    rm -f /tmp/_toolchain_check.o
  else
    fail "arm-none-eabi-gcc is on PATH but can't compile a trivial program"
    echo "    This exact failure mode hit this pilot once: Homebrew's arm-none-eabi-gcc"
    echo "    formula ships without newlib (no stdint.h etc). If that's what you have,"
    echo "    install the official ARM GNU Toolchain instead (no root needed):"
    echo "    https://developer.arm.com/downloads/-/arm-gnu-toolchain-downloads"
    echo "    Extract it anywhere and put its bin/ on PATH ahead of any Homebrew copy."
    cat /tmp/_toolchain_check.log 2>/dev/null | sed 's/^/    /'
    FAILED=1
  fi
else
  fail "arm-none-eabi-gcc not found on PATH"
  echo "    macOS:  download the official tarball (bundles newlib, no root needed):"
  echo "            https://developer.arm.com/downloads/-/arm-gnu-toolchain-downloads"
  echo "            (the Homebrew 'arm-none-eabi-gcc' formula is known-broken - see above)"
  echo "    Linux:  apt install gcc-arm-none-eabi  (or your distro's equivalent)"
  FAILED=1
fi

# --- Step 2: QEMU (optional) ------------------------------------------------
# Only needed for L0/L1 (compile/link) dynamic checks. Its STM32 USART model
# has a known bug (see recon/PLATFORM.md) so it can't dynamically verify
# runtime defects - that's what Renode (next step) is for.
info "2/5 - checking for QEMU (optional - boot/link-level checks only, see recon/PLATFORM.md for its known USART limitation)"
if command -v qemu-system-arm >/dev/null 2>&1; then
  pass "qemu-system-arm found ($(qemu-system-arm --version | head -1))"
else
  echo "    Not found. Optional - L0/L1 verification only needs the compiler above."
  echo "    macOS: brew install qemu   |   Linux: apt install qemu-system-arm"
fi

# --- Step 3: Renode (optional, recommended) --------------------------------
# The only tool in this setup that can dynamically prove a runtime fix works
# (real byte-level echo test - see renode/usart_irq_test.resc). Not on
# Homebrew's default tap reliably, so we point to the official portable build.
info "3/5 - checking for Renode (optional - the tool that actually closes the L2/L3 dynamic-verification gap QEMU can't; see renode/)"
if command -v renode >/dev/null 2>&1; then
  pass "renode found ($(renode --version 2>&1 | head -1))"
else
  echo "    Not found. Optional - only needed to re-run renode/usart_irq_test.resc."
  echo "    Official portable build (no installer, no root):"
  echo "    https://github.com/renode/renode/releases (look for *-portable.dmg / .tar.gz for your OS)"
  echo "    macOS: mount the .dmg, copy Renode.app anywhere, then:"
  echo "      xattr -dr com.apple.quarantine /path/to/Renode.app"
  echo "      ln -s /path/to/Renode.app/Contents/MacOS/renode /usr/local/bin/renode"
fi

# --- Step 4: fetch firmware at pinned commits -------------------------------
# Clone only if not already present (idempotent / safe to re-run), then
# always check out the pinned commit explicitly, even on an existing clone,
# in case someone previously ran `git pull` and moved it off the pin.
info "4/5 - fetching firmware (pinned commits, not 'latest')"
mkdir -p firmware
if [ -d firmware/libopencm3/.git ]; then
  pass "firmware/libopencm3 already present"
else
  git clone https://github.com/libopencm3/libopencm3.git firmware/libopencm3 || { fail "clone failed"; FAILED=1; }
fi
if [ -d firmware/libopencm3/.git ]; then
  ( cd firmware/libopencm3 && git checkout -q "$LIBOPENCM3_COMMIT" ) \
    && pass "libopencm3 checked out at pinned commit ${LIBOPENCM3_COMMIT:0:7}" \
    || { fail "could not check out pinned libopencm3 commit"; FAILED=1; }
fi

if [ -d firmware/libopencm3-examples/.git ]; then
  pass "firmware/libopencm3-examples already present"
else
  git clone https://github.com/libopencm3/libopencm3-examples.git firmware/libopencm3-examples || { fail "clone failed"; FAILED=1; }
fi
if [ -d firmware/libopencm3-examples/.git ]; then
  ( cd firmware/libopencm3-examples && git checkout -q "$LIBOPENCM3_EXAMPLES_COMMIT" ) \
    && pass "libopencm3-examples checked out at pinned commit ${LIBOPENCM3_EXAMPLES_COMMIT:0:7}" \
    || { fail "could not check out pinned libopencm3-examples commit"; FAILED=1; }
fi

# Don't attempt to build against a broken/missing toolchain - bail out early
# with a clear message instead of producing a confusing wall of compiler errors.
if [ "$FAILED" -eq 1 ]; then
  echo
  fail "Stopping before build - fix the toolchain issue above first."
  exit 1
fi

# --- Step 5: build ----------------------------------------------------------
# First the library itself (TARGETS=stm32/f4 limits the build to just our
# chip family instead of every MCU libopencm3 supports - much faster), then
# a clean rebuild of the actual firmware under test as a smoke test.
info "5/5 - building libopencm3 (STM32F4 target) and the example firmware"
( cd firmware/libopencm3 && make -j4 TARGETS=stm32/f4 >/tmp/_libopencm3_build.log 2>&1 ) \
  && pass "libopencm3 built" \
  || { fail "libopencm3 build failed - see /tmp/_libopencm3_build.log"; FAILED=1; }

EXAMPLE_DIR="firmware/libopencm3-examples/examples/stm32/f4/stm32f4-discovery/usart_irq"
if [ "$FAILED" -eq 0 ]; then
  # Remove any stale build artifacts first so this is a genuine clean-build
  # smoke test, not accidentally reusing an old .o/.elf from a previous run.
  ( cd "$EXAMPLE_DIR" && rm -f usart_irq.o usart_irq.elf usart_irq.map usart_irq.d \
      && make "OPENCM3_DIR=$SCRIPT_DIR/firmware/libopencm3" >/tmp/_example_build.log 2>&1 ) \
    && pass "usart_irq example built cleanly (smoke test passed)" \
    || { fail "example build failed - see /tmp/_example_build.log"; FAILED=1; }
fi

echo
if [ "$FAILED" -eq 0 ]; then
  info "Environment reproduced successfully."
  echo "Next: read recon/HYDRON_PROMPTS.md, or re-seed a defect from recon/DEFECT_CANDIDATES.md"
  echo "and rebuild with:"
  echo "  (cd $EXAMPLE_DIR && make OPENCM3_DIR=$SCRIPT_DIR/firmware/libopencm3)"
  if command -v renode >/dev/null 2>&1; then
    echo
    echo "Renode is available - to dynamically verify a defect (real byte-level echo test):"
    echo "  renode --disable-gui -P 4567 renode/usart_irq_test.resc &"
    echo "  python3 renode/echo_test.py"
    echo "See recon/DEFECT_CANDIDATES.md for which defects this can and can't actually catch."
  fi
else
  info "Setup incomplete - see the ✗ items above."
  exit 1
fi
