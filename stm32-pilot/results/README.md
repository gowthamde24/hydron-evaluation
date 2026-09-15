# results/ — comparison plots

Generated from `pilot/run_log.csv` (the single source of truth — every number
here traces back to a real, logged Hydron run, not an estimate). Regenerate
any time the CSV changes:

```
cd stm32-pilot
source .venv/bin/activate   # first time: python3 -m venv .venv && pip install matplotlib
python3 results/make_plots.py
```

## What each plot shows

| File | What it compares |
|---|---|
| `1_funnel_by_defect_class.png` | Surfaced → pointed at real cause → correct repair, broken out by defect class (L0 loud/compile, L1 loud/link, L2 semi-loud, L3 silent) |
| `2_verification_tier.png` | Every harness-half repair classified as dynamically verified (real Renode pass/fail), statically verified (rebuilt or byte-exact source match), plausible-but-unverified, or failed |
| `3_grounding_on_vs_off.png` | The 2 generation-grounding tasks, each run once with an explicit citation instruction (A-ON) and once without (A-OFF) — a 2×2 outcome grid, not an aggregated bar chart, since n=1 per cell |
| `4_pilot_vs_expanded.png` | Diagnosis/citation quality: the original 9-run pilot vs. everything added in the expanded campaign |
| `5_by_target.png` | Verification tier broken out by firmware target — the same 5-defect taxonomy applied to 5 different real example files (`usart_irq`, `miniblink`, `timer`, `button`, `usart` polling) |

## Status

37 runs logged (33 harness-half, 4 generation-half). This is the campaign's
final scope: the original 5-defect pilot on `usart_irq`, the same taxonomy
repeated across 4 more real firmware targets (`miniblink`, `timer`, `button`,
`usart` polling), all 8 shared-linker-script defects (`N2`,`T2`,`X2`,`U2`,
`F1`,`F2`,`C1`,`C2`), and one instance each of four capability-isolation
categories (`B2` no-bug control, `R1` red herring, `M1` multi-defect, `Q1`
ambiguous report) chosen to prioritize breadth of finding-type over repeated
sample size. The paired repeats of those four categories (`B3`,`R2`,`M2`,`Q2`)
and 4 new generation-grounding tasks (`GenE`-`GenH`) were deliberately
descoped to close out the campaign within a fixed time budget — a scope
decision, not an incomplete run.

Every run in this data set — including several instances of contamination,
false-success claims, and wrong-target diagnoses caught along the way — is
disclosed honestly in `run_log.csv`'s own notes, the same way the original
pilot's contamination findings were kept and reported rather than discarded.

`make_plots.py` never fabricates or interpolates — every count is read
directly from `run_log.csv`'s own columns (`loudness_class`,
`harness_surfaced`, `pointed_at_real_cause`, `repair_succeeded`,
`grounding_class`), with `repair_succeeded`'s free text keyword-matched into
one of 4 honest tiers (see the script's `verification_tier()` function for
the exact rule).
