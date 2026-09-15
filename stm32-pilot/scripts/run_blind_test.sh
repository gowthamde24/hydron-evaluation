#!/usr/bin/env bash
# run_blind_test.sh - Blind-test hygiene automation.
#
# Stashes recon/, pilot/, renode/, README.md, and prior transcripts out of
# the project before invoking Hydron, runs it non-interactively, then
# restores them. A mutex lock serializes stash -> run -> restore across
# concurrent invocations. Does NOT seed or revert the defect itself; that's
# an explicit git/sed command the caller runs before and after this script
# (see DEFECT_CANDIDATES.md for the change per defect ID).
#
# Usage:
#   ./run_blind_test.sh <prompt-file> <transcript-out-path> [session-title]
#
#   <prompt-file>          plain-text symptom report to send Hydron
#                          (see recon/HYDRON_PROMPTS.md)
#   <transcript-out-path>  where to write the raw session transcript, e.g.
#                          transcripts/N1_debug.log
#   [session-title]        optional --title for `hydron run`, defaults to the
#                          transcript filename
#
# Safe to re-run: refuses to stomp an existing transcript file, and the
# restore step is idempotent.

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

# firmware/libopencm3-examples is its own nested git clone (see setup.sh),
# invisible to a `git diff` run from PILOT_ROOT. The dirty-check runs inside
# that repo directly, to catch an unseeded defect before it wastes a run.
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

# transcripts/ needs to stay writable during the run itself (Hydron's own
# output is redirected there), so it's swapped for an empty dir instead of
# moved aside, and the new file spliced back in before restoring it. This
# keeps prior runs' narrated diagnoses out of Hydron's reach mid-session.
TRANSCRIPTS_STASH_DIR="$(cd "$PILOT_ROOT/.." && pwd)/.blind_test_transcripts.$$"

# Mutex over the whole stash -> run -> restore section: PID-unique paths
# alone still leave a window where one invocation restores files while
# another is mid-run. The lock closes that at the cost of serializing
# concurrent runs, which is the right trade against cross-run contamination.
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
