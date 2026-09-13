# Hydron Evaluation

An independent evaluation of **Hydron** (H2Loop), a hardware-aware AI coding
assistant for embedded engineers.

Two questions drove this work:

- Does Hydron's output actually ground in real hardware documentation, or
  does it just sound plausible?
- Can Hydron's execution harness reliably locate, diagnose, fix, and verify a
  real defect in real firmware?

Every claim in this report traces to a real, re-runnable test or a cited page
in a real reference document. Nothing here is asserted without evidence, and
nothing is presented with more confidence than the evidence supports.

---

## Contents

- [Target and setup](#target-and-setup)
- [Methodology](#methodology)
- [Findings](#findings)
- [Quantitative metrics](#quantitative-metrics)
- [Approaches to improve Hydron's execution harness](#approaches-to-improve-hydrons-execution-harness)
- [Threats to validity](#threats-to-validity)
- [Repository structure](#repository-structure)
- [References](#references)

---

## Target and setup

The evaluation targets a real **STM32F407** microcontroller running real
open-source firmware (`libopencm3`), checked against STMicroelectronics' own
official reference manual and datasheet. Every hardware fact used anywhere in
this evaluation is traceable to one of those two documents, with a section
and page number.

**Toolchain:** ARM GNU Toolchain (official release), `make`, QEMU, and
[Renode](https://renode.io) (Antmicro, open source) for dynamic,
byte-level verification of runtime behavior — chosen after QEMU's STM32 USART
model was found to have a specific, independently-confirmed limitation.
Full environment setup is scripted and reproducible (`stm32-pilot/setup.sh`).

## Methodology

Each test in this evaluation followed the same disciplined pipeline:

1. **Recon** — map the real firmware precisely, with exact file:line references
2. **Ground truth** — verify every hardware fact against an official manufacturer document — never from an AI's own knowledge
3. **Controlled fault injection** — introduce exactly one defect at a time, under version control
4. **Blind execution** — remove all internal analysis material from the working directory before invoking Hydron, so it investigates from the symptom alone
5. **Independent verification** — confirm the outcome by rebuilding and, where possible, by dynamic emulation — not by trusting Hydron's own account of success
6. **Revert and log** — return to a clean baseline and record the real, observed outcome before moving to the next test

Tests were also designed to separate three distinct capabilities that a
single "did it fix the bug" result would otherwise blur together:

| Capability | What it isolates |
|---|---|
| **Identify** | Can it locate the correct file/line from a symptom alone? |
| **Diagnose** | Can it explain *why* the symptom occurs, correctly? |
| **Execute** | Can it correctly use its own tools, and recover from its own mistakes? |

The exact defects, prompts, and seeding procedure are intentionally not
reproduced in this document — they're the evaluation's own working material,
kept in the private working files rather than a public write-up.

## Findings

- **Identification is reliable.** Across every test, Hydron correctly
  localized the true defect from a symptom description alone — including
  defect types it had not encountered elsewhere in this evaluation.

- **Diagnosis is strong, but not gated on the premise being true.** When a
  real defect was present, Hydron's causal explanations were consistently
  correct and well-grounded. However, diagnosis and *verifying the report is
  real* are treated as the same step — they are not.

- **The most significant finding: no reproduce-before-fix behavior.** Given a
  fabricated bug report describing a symptom that could not physically occur
  in the working code provided, Hydron did not attempt to confirm the
  symptom existed. It produced a plausible-sounding explanation and modified
  working code to "fix" a defect that was never there.

- **Execution reliability is the weakest of the three capabilities.** When a
  build failed, Hydron's self-correction did not consistently use the
  simplest, explicitly-documented fix — in one case, it modified shared
  build configuration rather than supplying a missing parameter the tool's
  own error message named directly.

- **Citation behavior depends on whether a source was actually checked, not
  on whether the answer is correct.** When explicitly instructed to ground
  its answer and cite a source, Hydron either produced a real, verifiable
  citation or explicitly declined to assert an unverified fact. Without that
  instruction, it produced confident, correct-sounding claims with source
  attribution it had not actually checked.

## Quantitative metrics

Every figure below is reported next to its sample size. For context: the
industry-standard benchmark for AI coding agents on real-world tasks
([SWE-bench](https://arxiv.org/abs/2310.06770)) evaluates thousands of task
instances and reports single-digit resolution percentages for leading models.
A percentage from a handful of controlled tests is a different kind of
evidence, and is not presented as equivalent.

| Metric | Result | Basis |
|---|---|---|
| Identification accuracy (Top-1 localization) | 100% on all tests; 100% on the blind subset alone | Standard fault-localization framing (Zhou, Zhang & Lo, ICSE 2012; Wong et al., IEEE TSE 2016) |
| Fix plausibility (matches known-good source) | 100% | — |
| Fix independently, dynamically verified | 40% | Distinct from plausibility — see below |
| Recall (real defects correctly found) | 100% | Standard defect-detection framing (Habib & Pradel, ASE 2018; Rutar et al., ISSRE 2004) |
| Precision (flagged defects that were real) | ≈83% | The one false positive is the fabricated-defect test above |
| Grounded citation rate, explicitly instructed | 100% avoided an unverified claim | — |
| Grounded citation rate, not instructed | 50% asserted an unverified claim as fact | — |

**The plausibility/verification gap is the number that matters most.** A fix
that merely *matches expected form* and a fix that is *independently
confirmed to work* are different claims — Automated Program Repair research
has studied this exact distinction for over a decade under the term
"plausible but incorrect" patches (Qi, Long, Achour & Rinard, ISSTA 2015).
This evaluation's own data shows the same gap: 100% plausible, 40%
independently verified.

## Approaches to improve Hydron's execution harness

These are recommendations about Hydron's own architecture and behavior —
not about how it should be tested.

1. **Add a reproduce-before-fix step to the execution harness itself.**
   Before generating a code change for a reported runtime symptom, the
   harness should attempt to independently observe that symptom — via build,
   emulation, or execution — and should decline to propose a fix, or flag
   low confidence, when the symptom cannot be reproduced.

2. **Constrain self-correction to the documented interface.** When a tool
   invocation fails with an error that names its own resolution (a missing
   parameter, a documented flag), the harness should apply that resolution
   directly rather than modifying shared configuration or infrastructure to
   route around the failure. A scope check — did the change stay within the
   task's own file boundary — would catch this automatically.

3. **Track and expose a distinct "verified" state, separate from "plausible."**
   The harness should distinguish, in its own output, between "this change
   matches the expected pattern" and "this change was independently confirmed
   to resolve the reported behavior," rather than reporting both as success.

4. **Calibrate confidence to verification method.** A citation backed by an
   actual document lookup and a citation stated from memory are not the same
   claim. The harness should represent this difference to the user rather
   than presenting both in the same confident register.

## Threats to validity

- This evaluation was executed and initially assessed by an AI system, not
  the human evaluator directly — findings should be independently reviewed
  against the raw evidence before being treated as final.
- Sample sizes throughout are small; results describe specific, observed
  behavior and should not be read as general reliability claims.
- Two of the runtime defect classes used in this evaluation cannot be
  dynamically verified with current open-source emulation tools, for
  structural reasons independent of any single tool's maturity.
- All fault injection and reversion was performed programmatically; changes
  were not independently re-inspected line-by-line before each test.

## Repository structure

```
hydron-evaluation/
├── README.md          this document
└── stm32-pilot/         the working evaluation environment
    ├── setup.sh          reproduces the full build/verification environment
    ├── firmware/          real open-source firmware under test (pinned versions)
    ├── references/        official manufacturer documentation, vendored for offline use
    ├── renode/            dynamic verification tooling
    ├── recon/             internal analysis and test design (private working material)
    ├── pilot/              results: logs, summary statistics, and diagrams
    └── transcripts/        raw, unedited session output — the primary evidence base
```

`stm32-pilot/setup.sh` reproduces the entire environment from a clean machine
in one step. Internal test design and the raw evidence base are preserved in
the repository for audit purposes but are not walked through here.

## References

- STMicroelectronics, *RM0090 Reference Manual* (STM32F405/407/427/429
  family), Doc ID 018909 Rev 4.
- STMicroelectronics, *STM32F405xx/407xx Datasheet*, DocID022152 Rev 8.
- Zhou, Zhang & Lo, "Where Should the Bugs Be Fixed?", ICSE 2012, pp. 14–24.
- Wong, Gao, Li, Abreu & Wotawa, "A Survey on Software Fault Localization," IEEE TSE, Vol. 42, No. 8, 2016, pp. 707–740.
- Qi, Long, Achour & Rinard, "An Analysis of Patch Plausibility and Correctness for Generate-And-Validate Patch Generation Systems," ISSTA 2015, pp. 24–36.
- Habib & Pradel, "How Many of All Bugs Do We Find? A Study of Static Bug Detectors," ASE 2018, pp. 317–328.
- Rutar, Almazan & Foster, "A Comparison of Bug Finding Tools for Java," ISSRE 2004.
- Smith, Barr, Le Goues & Brun, "Is the Cure Worse Than the Disease? Overfitting in Automated Program Repair," ESEC/FSE 2015, pp. 532–543.
- Sharma et al. (Anthropic), "Towards Understanding Sycophancy in Language Models," ICLR 2024, arXiv:2310.13548.
- Jimenez et al., "SWE-bench: Can Language Models Resolve Real-World GitHub Issues?", ICLR 2024, arXiv:2310.06770.
