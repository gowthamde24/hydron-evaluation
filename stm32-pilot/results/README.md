# results/

Comparison plots generated from `pilot/run_log.csv`. Every number traces
back to a real, logged Hydron run.

Regenerate any time the CSV changes:

```
cd stm32-pilot
source .venv/bin/activate
python3 results/make_plots.py
```

## Plots

| File | What it compares |
|---|---|
| `1_funnel_by_defect_class.png` | Surfaced, pointed at real cause, correct repair, by defect class (L0 loud/compile, L1 loud/link, L2 semi-loud, L3 silent) |
| `2_verification_tier.png` | Every harness-half repair: dynamically verified (real Renode pass/fail), statically verified (rebuilt or exact source match), plausible but unverified, or failed |
| `3_grounding_on_vs_off.png` | Generation-grounding tasks, run with an explicit citation instruction and without |
| `4_pilot_vs_expanded.png` | Diagnosis/citation quality: original pilot vs. expanded campaign |
| `5_by_target.png` | Verification tier by firmware target, same taxonomy across 5 real example files |

## Status

37 runs logged (33 harness-half, 4 generation-half). Final scope: the
original 5-defect pilot on `usart_irq`, the same taxonomy repeated across 4
more firmware targets, all 8 shared-linker-script defects, and one instance
each of four capability-isolation categories (no-bug control, red herring,
multi-defect, ambiguous report), chosen to prioritize breadth of
finding-type over repeated sample size within a fixed time budget.

Every run, including several instances of contamination, false-success
claims, and wrong-target diagnoses caught along the way, is disclosed
honestly in `run_log.csv`'s own notes.

`make_plots.py` never fabricates or interpolates. Every count reads
directly from `run_log.csv`'s own columns.
