# summary.md — STM32 pilot, n=9

Raw fractions only, no percentage with a
denominator under 10, nothing computed that this sample can't support. Two of the
nine runs are flagged and treated separately in the harness numbers below because
they were compromised (see `observations.md` OBS-2) — reported both ways rather than
quietly folded into a clean headline.

**Read this alongside two open items, not instead of them:**
1. Judgment calls below (`grounded_correct` etc.) were made by Claude, not by you.
   Treat this document as a draft pending your own read of the 9 transcripts in
   `../transcripts/`, not a finished finding.
2. This pilot used a rig (real toolchain, two emulators, git-based seed/revert
   automation) that is arguably the "test harness" the original brief's anti-goals
   ruled out. Flagging again here, in the numbers document, not just in the chat.

## Harness half (5 seeded defects: L0, L1, L2, L3, L3)

- Observability (harness surfaced the fault): **5 of 5**
- Localisation (pointed at the real file:line cause, given it surfaced): **5 of 5**
- Repair succeeded, dynamically confirmed independently of Hydron's own account:
  **2 of 5** — S2 (linker fix, confirmed by an actual successful rebuild) and S5
  (NVIC fix, confirmed by a real byte-echo test in Renode: broken with the defect
  seeded — genuine timeout — working again once reverted; see
  `../recon/DEFECT_CANDIDATES.md` and `../renode/`)
- Repair succeeded, correct by source-diff match but *not independently, dynamically
  confirmed* — for S3 and S4, this isn't a tooling gap still to be closed; testing
  against two independent simulators (QEMU, then Renode) showed neither can exercise
  a baud-rate or GPIO-pin-mux defect at all, a structural property of that class of
  tool, not a missing feature: **3 of 5** (S1, S3, S4)
- **Same two counts, split by contamination status**, since averaging them together
  would overstate what the clean data shows:
  - Clean, blind runs (S3, S4, S5): **3 of 3** surfaced, localised, and fixed
    correctly, with honest self-reported verification failure each time.
  - Compromised runs (S1, S2): **2 of 2** also surfaced, localised, and fixed
    correctly — but both had the answer available in a file Hydron read mid-run, so
    this pair is not evidence of diagnostic capability, only of "can copy a value out
    of a file it can read." Reported for completeness, not combined into the headline
    fraction above.

## Generation half (2 tasks × A-ON/A-OFF = 4 runs)

Grounding class by condition:

| condition | grounded_correct | lucky_correct | uncited | confident_wrong |
|---|---|---|---|---|
| A-ON (n=2) | 1 | 0 | 1 | 0 |
| A-OFF (n=2) | 0 | 1 | 0 | 1 |

Read across, not down — this is two conditions of one run each per task, not four
independent samples of the same thing. The pattern worth naming at n=2 per cell: in
this pilot, A-ON never produced a confident, unverified claim, and A-OFF never
produced a demonstrably-grounded one. Two prompt pairs is not enough to claim this
generalizes; it is enough to say it happened, plainly, both times it was tried.

## Cost

Aggregate, not per-run: **2.69 credits across 11 Hydron CLI sessions** today
(`hydron stats`), averaging **~0.24 credits/session**. This total includes the 9
formal runs plus 2 earlier ad hoc checks (an initial file-visibility sanity check,
and one non-`--auto` attempt that aborted on a permission prompt before doing any
work). I could not cleanly separate this aggregate into a verified per-run figure or
range without guessing at session-ID-to-run mapping, so I'm reporting the honest mean
across everything rather than fabricating a precise breakdown. If per-run cost
matters for CC-3's costing section, `hydron session export <sessionID>` on each of
the 11 listed session IDs would get exact numbers — not done here for time, flagged
as a real gap rather than papered over.

## What this pilot does and doesn't support claiming

Supports: on this one target, with real documentation available, Hydron correctly
diagnosed all 3 cleanly-tested runtime/build defects it was given as symptom reports,
and its citation behavior changed visibly (n=2) based on whether it was explicitly
told not to guess.

Does not support: any claim about Hydron's general reliability, its behavior on
larger or unfamiliar codebases, or its behavior once a human (not Claude) is doing
the judging instead of the running.
