#!/usr/bin/env bash
# =============================================================================
# run_blind_test.sh - Blind-test hygiene automation.
#
# Stashes recon/, pilot/, renode/, README.md, and prior transcripts out of
# the project before invoking Hydron, so it investigates from the symptom
# alone, then restores them. Concurrency-safe: a mutex lock serializes the
# whole stash -> hydron-run -> restore critical section across any number
# of parallel invocations, so one run can never expose another's stashed
# material mid-run. Does NOT seed or revert the defect itself; that stays
# an explicit git/sed command the caller runs immediately before and after
# this script (see DEFECT_CANDIDATES.md for the exact change per defect ID).
#
# Usage:
#   ./run_blind_test.sh <prompt-file> <transcript-out-path> [session-title]
#
#   <prompt-file>          plain-text file containing the exact symptom report
#                          to send Hydron (see recon/HYDRON_PROMPTS.md)
#   <transcript-out-path>  where to write the raw session transcript, e.g.
#                          transcripts/N1_debug.log
#   [session-title]        optional --title for `hydron run`, defaults to the
#                          transcript filename
#
# What it does, in order:
#   1. Verifies the defect has already been seeded (git status must show a
#      real diff) - refuses to run a "blind" test against an unmodified
#      working tree, since that's not a test of anything
#   2. Moves recon/, pilot/, renode/, and README.md out of the project to a
#      sibling temp directory (NOT /tmp - a sibling of stm32-pilot/, so it
#      survives if /tmp is cleared mid-run and stays easy to find if this
#      script is interrupted)
#   3. Runs `hydron run --auto` non-interactively, writing raw output to the
#      transcript path
#   4. Restores the stashed files, even if Hydron's run failed or was
#      interrupted (trap-based, not just a happy-path move-back)
#   5. Leaves the (now Hydron-edited) working tree in place for the caller to
#      verify (build / Renode) and revert
#
# Safe to re-run: refuses to stomp an existing transcript file, and the
# restore step is idempotent.
# =============================================================================

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PILOT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PILOT_ROOT"

PROMPT_FILE="${1:?usage: run_blind_test.sh <prompt-file> <transcript-out-path> [session-title]}"
TRANSCRIPT="${2:?usage: run_blind_test.sh <prompt-file> <transcript-out-path> [session-title]}"
TITLE="${3:-$(basename "$TRANSCRIPT" .log)}"

if [ ! -f "$PROMPT_FILE" ]; then
	echo "ERROR: prompt file not found: $PROMPT_FILE" >&2
	exit 1
fi

if [ -f "$TRANSCRIPT" ]; then
	echo "ERROR: transcript already exists, refusing to overwrite: $TRANSCRIPT" >&2
	echo "       (delete it first if you really mean to re-run this defect)" >&2
	exit 1
fi

# firmware/libopencm3 and firmware/libopencm3-examples are each their OWN
# nested git clones (see setup.sh) - invisible to a `git diff` run from
# PILOT_ROOT, which stops at the nested .git boundary. Every seeded defect
# in this campaign lives inside firmware/libopencm3-examples specifically
# (see DEFECT_CANDIDATES.md), so the dirty-check has to run inside THAT
# repo, not the parent one. Catches the "forgot to seed the defect" mistake
# before it wastes a real Hydron credit.
FW_REPO="$PILOT_ROOT/firmware/libopencm3-examples"
if (cd "$FW_REPO" && git diff --quiet && git diff --cached --quiet); then
	echo "ERROR: no seeded change detected in firmware/libopencm3-examples." >&2
	echo "       Seed the defect first (see recon/DEFECT_CANDIDATES.md), then re-run." >&2
	exit 1
fi

# A sibling of stm32-pilot/, not /tmp: stays visible and survives a cleared
# /tmp if this script is killed mid-run. PID-suffixed so concurrent
# invocations never collide on the same path.
STASH_DIR="$(cd "$PILOT_ROOT/.." && pwd)/.blind_test_stash.$$"
STASH_ITEMS=(recon pilot renode README.md)

# transcripts/ is handled separately from STASH_ITEMS: a run must still be
# able to WRITE its own new transcript during the run (the `hydron run ...
# > "$TRANSCRIPT"` redirect below), so it can't simply be moved aside like a
# read-only item. Prior runs' narrated diagnoses are a real crib source, so
# the real transcripts/ dir is swapped out for an empty one for the run's
# duration; the new file is spliced back in before restoring it.
TRANSCRIPTS_STASH_DIR="$(cd "$PILOT_ROOT/.." && pwd)/.blind_test_transcripts.$$"

# A mutex serializes the entire stash -> hydron-run -> restore critical
# section across every concurrent invocation of this script, for any
# target, via an atomic `mkdir`-based lock. PID-unique paths alone aren't
# enough under real concurrency: one invocation finding recon/pilot/renode
# already stashed by another still leaves a window where the first to
# finish restores them while the second is still mid-run. The lock makes
# that structurally impossible, at the cost of serializing wall-clock time
# under concurrency, which is the correct trade against silently
# contaminating another run's blind test.
LOCK_DIR="$(cd "$PILOT_ROOT/.." && pwd)/.blind_test.lock"
LOCK_HELD=0

release_lock() {
	if [ "$LOCK_HELD" = "1" ]; then
		rmdir "$LOCK_DIR" 2>/dev/null || true
		LOCK_HELD=0
	fi
}

acquire_lock() {
	local waited=0
	while ! mkdir "$LOCK_DIR" 2>/dev/null; do
		# Stale-lock safety: a crashed holder must not deadlock every future
		# run forever. 20 minutes is generous headroom over the "several
		# minutes" a single hydron run is expected to take.
		if [ -d "$LOCK_DIR" ]; then
			local age now mtime
			now=$(date +%s)
			mtime=$(stat -f %m "$LOCK_DIR" 2>/dev/null || echo "$now")
			age=$(( now - mtime ))
			if [ "$age" -gt 1200 ]; then
				echo "WARNING: lock at $LOCK_DIR is >20min old - assuming its" >&2
				echo "         holder crashed, and stealing it." >&2
				rmdir "$LOCK_DIR" 2>/dev/null || true
				continue
			fi
		fi
		if [ $(( waited % 30 )) -eq 0 ]; then
			echo "Waiting for another concurrent run_blind_test.sh invocation" >&2
			echo "to finish (shared blind-test lock held elsewhere) ... (${waited}s so far)" >&2
		fi
		sleep 2
		waited=$((waited + 2))
	done
	LOCK_HELD=1
}

restore_stash() {
	if [ -d "$STASH_DIR" ]; then
		echo "Restoring answer-key material from $STASH_DIR ..."
		for item in "${STASH_ITEMS[@]}"; do
			if [ -e "$STASH_DIR/$item" ]; then
				mv "$STASH_DIR/$item" "$PILOT_ROOT/$item"
			fi
		done
		rmdir "$STASH_DIR" 2>/dev/null || true
	fi
	# Splice this run's own new transcript (the only thing that can exist in
	# the temporary empty transcripts/ dir) into the real one, THEN restore
	# the real one - order matters, otherwise the new file is silently lost
	# when the temporary directory is removed.
	if [ -d "$TRANSCRIPTS_STASH_DIR" ]; then
		if [ -d "$PILOT_ROOT/transcripts" ]; then
			find "$PILOT_ROOT/transcripts" -mindepth 1 -maxdepth 1 \
				-exec mv {} "$TRANSCRIPTS_STASH_DIR/" \; 2>/dev/null
			rmdir "$PILOT_ROOT/transcripts" 2>/dev/null || true
		fi
		mv "$TRANSCRIPTS_STASH_DIR" "$PILOT_ROOT/transcripts"
	fi
	release_lock
}
# Runs on normal exit AND on interrupt/error - the whole point is that a
# killed or crashed run must never leave Hydron able to read the answer key
# on the *next* invocation because a restore step got skipped.
trap restore_stash EXIT INT TERM

echo "Acquiring the shared blind-test lock (serializes against every other" >&2
echo "concurrent target's stash/hydron-run/restore) ..." >&2
acquire_lock

if [ -d "$STASH_DIR" ]; then
	echo "ERROR: $STASH_DIR already exists - a previous run may not have cleaned up." >&2
	echo "       Inspect it by hand before continuing." >&2
	exit 1
fi
mkdir -p "$STASH_DIR"

echo "Stashing answer-key material out of the project (blind-test hygiene) ..."
for item in "${STASH_ITEMS[@]}"; do
	if [ -e "$PILOT_ROOT/$item" ]; then
		mv "$PILOT_ROOT/$item" "$STASH_DIR/$item"
	fi
done

# Swap the real transcripts/ (every prior run's full narrated diagnosis) out
# for a fresh, empty one - this run can still write its own new transcript
# into it, but cannot read or grep any other run's. Spliced back together in
# restore_stash above.
if [ -d "$PILOT_ROOT/transcripts" ]; then
	mv "$PILOT_ROOT/transcripts" "$TRANSCRIPTS_STASH_DIR"
fi
mkdir -p "$PILOT_ROOT/transcripts"

export PATH="$HOME/.hydron/bin:$PATH"

echo "Running Hydron (blind, --auto, non-interactive), logging to $TRANSCRIPT ..."
mkdir -p "$(dirname "$TRANSCRIPT")"
hydron run --auto --dir "$PILOT_ROOT" --title "$TITLE" "$(cat "$PROMPT_FILE")" \
	> "$TRANSCRIPT" 2>&1
HYDRON_EXIT=$?

# restore_stash (and, inside it, release_lock) runs automatically here via
# the EXIT trap.

echo "Done. Hydron exit code: $HYDRON_EXIT. Transcript: $TRANSCRIPT"
echo "Next: verify the result (build / Renode as appropriate), then revert the"
echo "seeded defect with 'git checkout -- <file>' before seeding the next one."
exit "$HYDRON_EXIT"
