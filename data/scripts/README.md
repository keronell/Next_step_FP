# scripts/

All Python scripts for data collection, labeling, annotation, and validation. Run from the project root.

## Matcher training environment

The Phase 2/3 matcher scripts (`evaluate_matchers.py`, `train_models.py`,
`export_model.py`, and the shared `nn_model.py` they both import) run in a
virtualenv of **their own**, built from a hash-pinned lockfile:

```bash
python -m venv data/venv-training
data/venv-training/bin/python -m pip install --require-hashes -r data/requirements-training.txt
data/venv-training/bin/python data/scripts/evaluate_matchers.py
```

(Paths follow the repo's POSIX convention, as in root `CLAUDE.md`. On Windows,
`Scripts/` replaces `bin/` in every venv path on this page.)

Not `backend/venv` — that one runs the service test suites, so every install into
it is an opportunity to move `numpy` or `pandas` under `dataset_digest()`, which
hashes feature and label *content*. Not root `requirements.txt` either: root is
entirely unpinned (`numpy>=1.20.0`, `pandas>=2.0.0`), and nobody deploying the
services needs torch.

Three mechanisms, none of them substitutes for the others:

| mechanism | job |
|---|---|
| `data/requirements-training.txt` | **prevents** environment drift |
| `dataset_digest()` (`dataset_guards.py`) | **detects** it |
| `env_manifest.py`, embedded in every report and verdict | **attributes** a number to an environment |

The lockfile resolves for one platform and interpreter — it is a single-machine
reproduction guarantee, not a cross-platform one. See the header of
`requirements-training.in` for what that costs elsewhere.

To change a pin, edit `data/requirements-training.in`, recompile with the exact
command in its header (all three flags matter — a missing one silently yields a
different lockfile), then re-run `evaluate_matchers.py` and confirm the digest is
unmoved. If it moved, no number from that environment is comparable to recorded
history — re-pin rather than re-baseline silently.

`env_manifest.py` is stdlib-only and its tests run under the service-test venv,
which proves it adds no dependency to the scripts that import it:

```bash
backend/venv/bin/python -m pytest data/scripts/tests -q
```

`test_nn_model.py`, `test_cross_fitted_temperature.py` and
`test_residual_matcher.py` need torch, so all three skip whole there and run in the
training venv instead:

```bash
data/venv-training/bin/python -m pip install pytest   # test tooling, see below
data/venv-training/bin/python -m pytest data/scripts/tests -q
```

**pytest is deliberately not in `requirements-training.txt`.** The lockfile's job
is to make the numbers reproducible, and a test runner is not part of producing
them — pinning it would put an unrelated dependency tree (and its future
resolution) inside the guarantee that protects the dataset digest. It is installed
separately, and installing it moves none of the pinned packages (verified: numpy
2.4.6, pandas 2.3.3, pyarrow 24.0.0, scikit-learn 1.8.0, lightgbm 4.6.0, torch
2.12.0 unchanged before and after).

### Reproduction record (DEV-87, 2026-07-27)

`evaluate_matchers.py` was run **before any manifest wiring existed**, on source
byte-identical to commit `00ca4af`. It reproduced
`dataset_digest 2bdd5ec99d6a49a2a19c40163cf7a69d560453e3095bc6b4241c6065f18a4b27`
and the recorded Gate-1 metrics exactly (logistic ECE 0.034099440082920096 /
stability 0.637516702641587; lightgbm 0.128155228434309 / 0.5566450817144618) —
`baseline_evaluation.md` came back byte-identical apart from its `Generated:`
timestamp. The manifest was added only afterwards, and the run was repeated: same
digest, same metrics, and the report diff is exactly the added `## Environment`
section. The manifest touches report text and one additive JSON key; it enters no
computation.

`model_selection.md` / `gate2_winner.json` are wired for the manifest but **not
regenerated here**: the Gate-2 re-baseline is sequenced after the cross-fitted
temperature fix (plan Step 4.2, execution-order item 5), and re-running Phase 3
now would break the recorded Gate-2 numbers ahead of that deliberate break.

### Reproduction record (DEV-90, 2026-07-27)

Adding the neural matcher to the Gate-1 candidate list must change what is
*measured*, never what the measurement is computed on. It didn't:

- `dataset_digest` still
  `2bdd5ec99d6a49a2a19c40163cf7a69d560453e3095bc6b4241c6065f18a4b27`.
- `logistic` ECE `0.034099440082920096` / stability `0.637516702641587` and
  `lightgbm` `0.128155228434309` / `0.5566450817144618` reproduced to the last
  digit — the incumbents' entries in `gate1_verdict.json` are bit-identical to the
  DEV-87 run.
- `gate1_verdict.json` gained a `small_nn` entry under `metrics` and one additive
  top-level key, `reported_not_gated`. No key was removed or reshaped.

`small_nn` **qualified**: ECE 0.062 (floor 0.10), top-2 stability 0.615 (floor
0.60). That is the first time it has been scored by the gate at all rather than
asserted about in a Phase-3 report — but note it clears stability by 0.015, and it
is the *ranking* that is the product, so treat the margin as thin until the sweep
(execution-order item 6) reports seed variance around it. Qualified is also only
the first of the four states in `CONTEXT.md`: it says nothing about Selected,
Servable or Deployable.

Its reseeded stability — reported, never gated — is **0.667**, measured on the same
outer folds, inner resamples and test rows as the gated 0.615 so the two differ in
what varies and nothing else. Measuring it on the *full* outer training partition
instead reads 0.706, and that number is wrong to print beside the gated one: the
0.04 gap is partly the larger training set, not seed robustness. Nearly three times
the margin by which the model clears the floor.

`small_nn`'s Gate-**2** numbers in `model_selection.md` are now stale: sharing
`nn_model.py` re-seeds the network per fit, where the inline version inherited
accumulated process-global torch RNG state. They are re-baselined with the
cross-fitted temperature, not piecemeal.

### Reproduction record (DEV-91, 2026-07-28)

The cross-fitted-temperature fix and the one-time Gate-2 re-baseline. This is the
first record here where numbers are *supposed* to move, so it is split in two.

**Unmoved, verified rather than asserted.** `evaluate_matchers.py` was re-run on
unchanged code before the fix and reproduced everything to the last digit: digest
`2bdd5ec99d6a49a2a19c40163cf7a69d560453e3095bc6b4241c6065f18a4b27`, `logistic`
ECE `0.034099440082920096` / stability `0.637516702641587`, `lightgbm`
`0.128155228434309` / `0.5566450817144618`, `small_nn` `0.061831` / `0.615315`,
reseeded `0.667016`. The regenerated report differed from the committed one by its
`Generated:` timestamp and nothing else. Gate 1 is unaffected **structurally**, not
just empirically: it gates on RAW ECE, has never applied a temperature, and
`evaluate_matchers.py` does not import `train_models.py` in either direction.

**Moved, deliberately.** Every Gate-2 `ece_scaled`/`temperature` in
`model_selection.md` and `gate2_winner.json`, per ADR 0004. All four models were
re-baselined in ONE run. Three results worth carrying forward:

- **`gbt_tuned` and `logistic_tuned` reproduce the old protocol exactly.** The new
  `ECE pooled-T (legacy)` column recomputes what the old code printed: 0.047 and
  0.103, matching the 2026-07-19 record, with pooled Phase-3 temperatures 1.65 and
  1.00 also matching. Their raw OOF is untouched, so their entire movement is the
  protocol. Their top-2 cannot move at all — temperature scaling is monotone within
  a row.
- **`small_nn`'s two causes are each ~0.023 and nearly cancel.** Recorded 0.101 ->
  legacy 0.078 is DEV-90's per-fit re-seeding alone; legacy 0.078 -> cross-fitted
  0.102 is DEV-91 alone. The net move from the recorded number is ~0.001.
  Attributing that net to cross-fitting would have been wrong in both magnitude and
  sign — the trap this ticket was warned about, and it materialised.
- **The bias has no reliable direction in either metric.** The guarantee is
  family-relative: a pooled temperature is the argmin of NLL on its own pool *among
  constant temperatures*, which is what makes the old number a fitted minimum
  rather than a measurement. Cross-fitting leaves that family — five per-fold
  constants absorb fold-specific miscalibration one constant cannot — so it can
  score lower, and here it does: cross-fitted ECE is lower for three of four models
  and cross-fitted NLL is lower for `logistic_tuned`. ADR 0004's "optimistic" is
  annotated accordingly. The decision is unaffected: the defect is that the number
  was never a held-out estimate, which holds whichever way it moves.

`two_tower` moved for a second reason of its own: it seeds from process-global torch
RNG rather than per fit (unlike `nn_model.NNClassifier`), so the three extra fits
per fold that cross-fitting inserts shift it. Reproducible from a clean run, but
order-dependent. Left as-is deliberately — making it deterministic would have been a
second uncontrolled change to a model's identity inside the run meant to
re-baseline it. Worth its own ticket.

`export_model.py` requires the Phase-3 calibration record rather than silently
defaulting, but does not transfer its temperature: `logistic_tuned` selected
heterogeneous Cs across folds, while the artifact serializes one fixed C. The
exporter therefore refits on pooled OOF predictions from the exact selected
configuration. On this dataset Phase 3 records **1.00**, while fixed `C=1.0`
reproduces **1.05**; the regenerated artifact now slightly softens served
`matchPercent` values through the DEV-88 inference path.

### Reproduction record (DEV-92, 2026-07-29)

The Residual Matcher (`nn_model.ResidualMatcher`, plan Step 2.3, ADR 0003). Adding
a model must not perturb the models already scored, and it didn't — **nothing moved
at all**, in either gate. Both re-runs were made from `data/venv-training` (the
hash-pinned stack of DEV-87; `Scripts/` on this Windows machine) on the final state
of the code, not an earlier one:

- `evaluate_matchers.py` re-run: `dataset_digest` still
  `2bdd5ec99d6a49a2a19c40163cf7a69d560453e3095bc6b4241c6065f18a4b27`; `logistic`
  ECE `0.034099440082920096` / stability `0.637516702641587`, `lightgbm`
  `0.128155228434309` / `0.5566450817144618`, `small_nn` `0.061831` / `0.615315`,
  reseeded `0.667016`. `gate1_verdict.json` and `baseline_evaluation.md` came back
  byte-identical apart from their timestamps, so the regenerated files were
  reverted rather than committed.
- `train_models.py` re-run: all four Gate-2 rows identical to the DEV-91
  re-baseline — `gbt_tuned` 0.892 / 0.040, `logistic_tuned` 0.849 / 0.061,
  `small_nn` 0.845 / 0.102, `two_tower` 0.763 / 0.081 (top-2 / cross-fitted ECE).
  `model_selection.md` and `gate2_winner.json` likewise differ only by timestamp
  and were reverted.

Three reasons that is worth stating rather than assuming, because two changes here
touched code that produced the recorded numbers:

- **`fit_logistic` now delegates to `nn_model.frozen_logistic`.** The Residual
  Matcher's paired-comparison argument rests on its frozen base being exactly the
  Incumbent's configuration, and a comment claiming so enforces nothing — so there
  is one construction site. The re-run is what shows the delegation is inert.
- **`NNClassifier.predict_proba`'s standardize-and-forward block moved into
  `_mlp_output`**, shared with `ResidualMatcher.predict_proba` so the two cannot
  hold drifting copies of a scaler contract fitted on training rows only. The
  arithmetic is unchanged, and `small_nn`'s two gate rows reproducing to the last
  digit is what shows it.
- **`two_tower` did not move, and that was arranged rather than lucky.** It seeds
  from process-global torch RNG rather than per fit, so its predictions depend on
  how many torch fits preceded them (DEV-91 documented this instead of fixing it).
  The Residual Matcher is deliberately **not** wired into `train_models.main()`, so
  no torch fit was inserted ahead of `two_tower` and its ordering is untouched.
  Whoever wires the sweep in must order it after `two_tower` or fix that seeding as
  a separate, separately-reported change.

Why it is not in `main()`: it is one of the fourteen Variants of the round-1 sweep
(execution-order item 6). Entering it in Gate 2 now would select its configuration
under a different protocol than the one every other Variant competes under. What
landed is the model plus the selection seam the sweep consumes —
`select_residual_config` (inherits the fold's tuned-logistic `C`, then grid-argmaxes
`alpha` on inner-CV top-2), `fit_residual`, and `alpha_zero_verdict`, which encodes
the pre-registered ">= 3 of 5 folds at alpha=0 means no non-linear signal found"
rule in one place so the sweep reads it rather than restating it.

**No `alpha` has been selected on the real data.** Nothing in this record is
evidence about whether a non-linear residual helps.

Test counts: `data/scripts/tests` is **41** under the training venv (was 23), and
**7 passed + 3 skipped** under `backend/venv` (was 7 + 2) — `test_residual_matcher.py`
is the third module that skips whole there, for the same reason as the other two:
no torch. The five service suites were re-run and are unchanged at **268**
(questionnaire 18, matching 108, roadmap 30, auth 31, history 81); no file under
`services/` is in this change.

### Reproduction record (DEV-93, 2026-07-29)

Round 1 of the neural rework: the nested 14-Variant sweep
(`sweep_variants.py`, plan Steps 2.2/2.4/2.5/2.7), plus wiring the Residual Matcher
into the Gate-2 run. Split like the DEV-91 record, because some numbers were
supposed to move and most were not.

**Unmoved, verified rather than asserted.** `train_models.py` was re-run on the
final state of the code and **all four DEV-91 Gate-2 rows came back to the digit** —
`gbt_tuned` 0.892 / 0.040, `logistic_tuned` 0.849 / 0.061, `small_nn` 0.845 / 0.102,
`two_tower` 0.763 / 0.081 (top-2 / cross-fitted ECE). `dataset_digest` still
`2bdd5ec99d6a49a2a19c40163cf7a69d560453e3095bc6b4241c6065f18a4b27`. Gate 1 was not
re-run and `gate1_verdict.json` is untouched; the sweep *reads* it for the Ship
Floor thresholds and quotes its numbers back rather than transcribing them.

**`two_tower` did not move, and that was arranged rather than lucky** — the trap the
DEV-92 record warned the next ticket about. It seeds from process-global torch RNG
rather than per fit, so its predictions depend on how many torch fits precede them,
and this ticket adds a fifth model that fits torch. The Residual Matcher is
therefore scored **after** `two_tower` in `main()`. `NNClassifier.fit` restores
every global generator it touches, so in principle position should not matter;
ordering it last means the claim does not have to rest on that reasoning being
right. Its seeding is still unfixed and still worth its own ticket.

**Moved, deliberately.** `model_selection.md` and `gate2_winner.json` gain a fifth
model, `residual_matcher`, and a `residual_alpha_verdict` key. The Gate-2 winner
(`gbt_tuned`) and the deployable selection (`logistic_tuned`) are unchanged, so
`export_model.py` is unaffected.

**The finding, and it is negative.** `alpha = 0` was selected in **5 of 5** outer
folds, so the pre-registered ADR 0003 rule fires: *no non-linear signal found*, and
the Residual Matcher is disqualified from being the shipped neural model. Its row is
identical to `logistic_tuned`'s in every column — which the report now *computes*
and explains rather than leaving two matching lines for a reader to puzzle over. At
`alpha = 0` the model is exactly logistic at its inherited `C`, and that `C` comes
from the same `select_by_inner_cv` call `logistic_tuned` uses (per-fold `C`
`[4.0, 4.0, 4.0, 0.05, 0.25]` for both), so the two are the same estimator fold for
fold. The rows are one measurement printed twice.

**New, and NOT comparable to any of the above.** `data/training/nn_rework.md` and
`round1_results.json` come from a **5-seed protocol** where each experiment seed is a
complete nested run varying fold partition *and* initialisation. They are a
different measurement from the single-seed Gate-2 path, not a later reading of it.
The sweep also trains on hard labels throughout, so its control Variant is the
*Gate-1* `small_nn` configuration, not the soft-target Gate-2 row. Headline results:

- **18 of 25 (seed, outer fold) selections resolved to the Residual Matcher at
  `alpha = 0`**, i.e. to exactly logistic regression. The 12 pure-MLP Variants —
  every capacity and regularization Variant, three protocol ones, and the V0 control
  — were selected **0 times between them**. On seed 45 the selected "neural" matcher
  and `logistic_tuned` disagree on **0 of 232** profiles.
- The alpha=0 rule fired in **4 of 5 seeds**.
- Paired bootstrap, **profile as the sampling unit**: vs `logistic_tuned`
  delta −0.0026, CI [−0.0095, +0.0043], sign holding in 2 of 5 seeds. vs `gbt_tuned`
  delta −0.0284, sign holding in 5 of 5, CI [−0.0595, +0.0026] — per-seed
  consistency and the interval disagree in flavour, which is why both are reported.
- **Ship Floor at the gated partition: the hard half clears, the mitigable half
  fails.** Stability 0.655 (floor 0.60, determinism assertion passed first); raw ECE
  0.122 (floor 0.10).
- **Re-measured under all 5 experiment seeds, the two halves are not equally solid.**
  Stability clears in **5 of 5** (mean 0.666 +/- 0.009, min 0.655), so the hard floor
  is not an artifact of the partition that happened to be gated. Raw ECE clears in
  **4 of 5** — the gated seed 42 is the only one that fails it (0.084 to 0.122, mean
  0.100). The gated verdict stands, because Gate 1's convention is one fixed
  partition and changing it after seeing the data would be moving a threshold; but
  reading it as "this configuration is miscalibrated" would be wrong. This check was
  added after code review pointed out that a hard, unmitigable floor was resting on a
  single draw while every other number in the deliverable was a 5-seed measurement.

**The ECE failure is about `C`, not about neural capacity, and that was checked
rather than reasoned.** The evaluated configuration contains no neural parameters,
and raw ECE is strongly sensitive to the inherited `C`: 0.290 at `C=0.05`, 0.122 at
`C=0.25`, **0.034 at `C=1.0`**, 0.098 at `C=4.0` — the identical estimator, through
the same `cv_oof_and_stability` path. Inner CV selected every value in the grid
across the 25 folds. So the floor is failed at the modal `C` and comfortably cleared
at another value of the same grid.

**Two plan errors were corrected in `docs/dev-23-nn-rework-plan.md`, not patched
around.** `GBT_GRID` is a `product` of four 2-element lists — **16** points, not the
"32-point grid" rev 3 claimed (and not at `train_models.py:53`), so the "less search
than the Incumbent" argument was overstated by 2x; 14 Variants against 16 is
*comparable* search, which still defeats "the NN was tuned harder" but supports no
claim of restraint. And Step 2.4 was still arguing from the pre-DEV-91 gap of 0.008
while a footnote contradicted it; the real gap is **0.004**, one profile, and the
corrected figures are now in the argument itself.

**Two biases in the contest, pointing in opposite directions, both disclosed.**
Inner-CV ties break by registry order, which favours the earliest-declared
(lower-capacity) Variants — they won 0 selections, so that one demonstrably decided
nothing. The second is more serious and the report states it plainly after code
review sharpened it: the Residual Matcher's `alpha` is resolved by argmax over 4
values **on the same inner splits that then rank all 14 Variants**, so it enters the
contest carrying a maximum over 4 configurations while each pure-MLP Variant
contributes a single score. That is optimistically biased in its favour and
mechanically helps explain 23/25. It is **not Leakage** in `CONTEXT.md`'s sense — no
held-out row is touched — but selection optimism inside the training partition, and
calling it merely "one extra search" (as an earlier draft did) understated it. It is
left in place because removing it means selecting `alpha` at a third nesting level,
which ADR 0003 considered and declined. It does not change the direction of the
finding: the Residual Matcher won mostly *at `alpha = 0`*, so the extra freedom it
enjoyed was the freedom to switch its neural branch off.

`evaluate_matchers.cv_oof_and_stability` gained a `random_state` parameter for the
across-seed Ship Floor measurement. **The default is the Gate-1 partition and every
recorded Gate-1 metric was verified to reproduce to the last digit through it** —
`logistic` ECE `0.034099440082920096` / stability `0.637516702641587`, `lightgbm`
`0.128155228434309` / `0.5566450817144618`, `small_nn` `0.06183095636038942` /
`0.6153150375167026`. Verified by calling the function directly rather than by
regenerating `gate1_verdict.json`, which is byte-unchanged by this ticket.

The sweep **checkpoints per experiment seed** to
`data/training/round1_checkpoint.json` (gitignored). Re-running after all seeds are
complete regenerates the report without refitting anything.

Test counts: `data/scripts/tests` is **55** under the training venv (was 42), and
**7 passed + 6 skipped** under `backend/venv` (was 7 + 3) — the three new modules all
skip whole there for the usual reason, no torch. `test_paired_bootstrap.py` was
verified to fail **5/5** against a row-resampling implementation before being kept.
The five service suites are unchanged at **268** (questionnaire 18, matching 108,
roadmap 30, auth 31, history 81); no file under `services/` is in this change.

### Reproduction record (DEV-95, 2026-07-30)

Round 2 of the neural rework and the **final** Ship Floor verdict (`sweep_round2.py`,
plan Step 2.7). Split like the DEV-91 and DEV-93 records: one number was supposed to
move and a great many were not.

**Unmoved, verified rather than asserted.** This ticket edits `select_by_inner_cv`,
which every nested selection in the pipeline goes through, so "inert" had to be shown
three ways rather than argued once:

- **The six Gate-1 metrics**, recomputed by calling `cv_oof_and_stability` and
  `reseeded_stability` **directly** rather than by regenerating `gate1_verdict.json`,
  which this ticket leaves byte-unchanged: `logistic` ECE `0.034099440082920096` /
  stability `0.637516702641587`, `lightgbm` `0.128155228434309` /
  `0.5566450817144618`, `small_nn` `0.06183095636038942` / `0.6153150375167026`,
  reseeded `0.6670161373214101`. All six to the last digit. (Build `X` with
  `dtype=float` as `evaluate_matchers.main()` does; `train_models.load_data()` uses
  float32 and the wrong one moves Gate-1 ECE by ~2.6e-8, which looks like a
  regression and is not.)
- **The five Gate-2 rows.** `train_models.py` re-run: `model_selection.md` and
  `gate2_winner.json` came back differing **only** in their timestamps, so
  `gbt_tuned` 0.892 / 0.040, `logistic_tuned` 0.849 / 0.061, `small_nn` 0.845 / 0.102,
  `two_tower` 0.763 / 0.081 and `residual_matcher` 0.849 / 0.061 all reproduce. The
  regenerated files were reverted rather than committed.
- **Round 1's entire deliverable.** `sweep_variants.py` re-run: `nn_rework.md` and
  `round1_results.json` came back byte-identical apart from their timestamps —
  including the Ship Floor and C-sensitivity tables, which that script *recomputes*
  rather than reading from its checkpoint. Reverted. `dataset_digest` still
  `2bdd5ec99d6a49a2a19c40163cf7a69d560453e3095bc6b4241c6065f18a4b27` throughout.
- **`two_tower`'s ordering is untouched** — `train_models.main()` is not modified, so
  the Residual Matcher still runs after it and the process-global-torch-RNG hazard the
  DEV-92 record raised is unchanged. Still unfixed, still worth its own ticket.

**The instrumentation, and why it is an out-parameter.** Round 1 computed a 14-way
inner-CV contest 25 times and kept only the argmax, so when ADR 0003's rule
disqualified the winner its own output could not name the replacement the rule owes.
`select_by_inner_cv` gained `scores_out=`, an optional list receiving `(params, score)`
for every grid point. It has six call sites and `test_residual_matcher.py` asserts on
its return value directly against an inherited `C`; widening the return type would have
changed what four callers receive to serve a need only one of them has.
`test_variant_scoreboard.py` pins both halves — the vector is recorded, and the answer
does not move when the channel is absent.

**New, and NOT comparable to Round 1's headline row.** `data/training/nn_rework_round2.md`,
`round2_results.json` and `round2_scoreboard.json`. Round 2's candidate set **excludes**
the Residual Matcher, so its `sweep_nn` column describes a different set of eligible
models; the two rounds share protocol, folds, seeds and comparators and nothing else.
Round 1's numbers stand unchanged.

- **The recovered scoreboard reproduces Round 1 exactly**: all 25 per-fold selections
  identical, which is the gate on every other number in the round.
- **The best genuinely non-linear Variant is `C3_seed_ensemble`** (mean inner-CV top-2
  0.7991 +/- 0.0236). That is the substitution ADR 0003 owed. Its cost, paired per
  contest: the disqualified Residual Matcher scored **+0.0280** above it on the
  selection metric, level in 2 of 25 contests.
- **The finding Round 1's selection counts could not express:** ensembling V0 is worth
  **+0.0353** against the same base — larger than that substitution cost, and larger
  than the whole capacity-plus-regularization spread. Seed-averaging was the only lever
  Round 1 moved, which is why all six refinements sit on it.
- **Round 2 earned its budget:** refinements took **22 of 25** selections. Selected:
  **`D5_ensemble_dropout_0.5_wd_1e-2`** — 5 `NNClassifier` members at dropout 0.5 and
  weight decay 1e-2, seeds `random_state + i`, everything else V0. Full specification
  (defaults included, read from the constructor signature) is in the report and
  `round2_results.json`, because DEV-97 exports it and a Variant name is not a
  specification. **It is 5 networks, not one**, and DEV-97 inherits that cost;
  explainability is unaffected, since IG over a probability-averaged ensemble is the
  average of the members' attributions.
- **That selection was a tie on count, and the tie-break is disclosed rather than
  buried.** `D5` and `D2_ensemble_dropout_0.5` each took 7 of 25, and `max()` over the
  counts would have resolved it by **registry order** — declaration order in a Python
  dict deciding which model gets exported. It is instead resolved on the contest's own
  metric (mean inner-CV top-2: D5 0.8110 with 7 contests won outright, D2 0.8065 with
  4), and **both arms are Ship-Floor-scored** so the choice hides nothing. No rule for
  aggregating per-fold winners into one configuration had been pre-registered, so this
  resolves a tie rather than moving a threshold. Both reach the same verdict.
- **Effect size, profile as the sampling unit:** vs `logistic_tuned` delta −0.0181,
  CI [−0.0440, +0.0060], sign in 4 of 5 seeds, materiality marker NOT cleared. vs
  `gbt_tuned` delta −0.0440, CI [−0.0750, −0.0138] (excludes zero), sign in 5 of 5.
- **The substitution priced on the deliverable's own metric, not just the selection
  one.** ADR 0003 asks for the cost explicitly, and the inner-CV margin is the quantity
  the choice was made on rather than the one a model is read by. Round-2 selected minus
  Round-1 selected, exactly paired over the same seeds and partitions and refitting
  nothing: delta **−0.0155** on pooled OOF top-2, CI [−0.0388, +0.0060] — 3.6 profiles
  of 232. That is not the two rounds as a series; it is the price of a candidate set
  that excludes the Residual Matcher against one that included it.
- **FINAL Ship Floor: the hard half clears, the mitigable half fails.** Stability
  **0.735** at the gated partition and **5 of 5** seeds (mean 0.716 +/- 0.011, min
  0.703) — a wider margin than Round 1's 0.666 and than the Incumbent `logistic`'s
  0.6375. Raw ECE **0.139**, clearing on only **1 of 5** partitions. So it ships as the
  **ranking** source with displayed percentages falling back to the formula's (ADR
  0002).
- **That ECE failure differs from Round 1's in kind, not degree.** Round 1's cleared on
  4 of 5 partitions, so its gated failure was a partition effect and reading it as
  "this model is miscalibrated" would have been wrong. Four of five fail here. The
  mitigation is what makes this model shippable, not an argument that the number is
  unrepresentative.

**Three disclosures the report carries, all counted rather than argued.** (1) The
per-contest registry-order tie-break decided **5 of 25** contests and the selected
Variant appears in tied groups, so for those contests the record cannot distinguish a
tie-broken pick from a decisive one — Round 1 could disclose the same bias and then
show it decided nothing, and that reassurance does not transfer. (2) The selection did
not converge: 8 different Variants won contests and the top count was 7 of 25 (28%),
against Round 1's 23 of 25, so "the selected configuration" is the modal answer of an
unstable selection. (3) The neural search total is now 20 configurations against
`gbt_tuned`'s 16 — "the NN was not tuned harder than the alternatives" was true after
Round 1 and is no longer true.

**The comparator legs are Round 1's, reused and verified rather than assumed.**
`gbt_tuned` and `logistic_tuned` do not depend on the Variant registry and the fold
partition is a function of the seed alone, so recomputing all five seeds would be an
hour of LightGBM nested CV reproducing a file this tree holds. Seed 42 was recomputed
from scratch anyway: identical top-2 and **0 of 232 profiles disagreeing** for both.
`--recompute-comparators` refits all five on a tree without the checkpoint.

**`sweep_round2.py --stage report`** re-renders the report from `round2_results.json`
alone — not from the gitignored checkpoint — refitting nothing, and refreshes the keys
derived from the per-fold scoreboard so the JSON and the report cannot carry different
versions of one derivation. It is not a convenience: Round 2's expensive tail (Ship
Floor evaluations of 5-member ensembles, twice over once the count tie was resolved
honestly) runs *after* the checkpointed seed loop, so a wording change would otherwise
be paid for in compute — and this run needed it twice, once because the first render
crashed on a bug already fixed in the working tree that the long-running process had
loaded before the fix.

**A code review changed the deliverable, and that is recorded rather than smoothed
over.** It caught that `D2` and `D5` were tied at 7 selections each and that `max()`
was resolving the shipped configuration by registry order, while `D5` led the contest
on the metric — and that the report's headline claimed the selected Variant "leads the
contest" by testing whether *any* refinement led it. The tie-break, the headline
derivation, and the ship-floor scoring of both arms are the fix. It also caught two
paths that read the gitignored `round1_checkpoint.json` unconditionally, which made
`--recompute-comparators` and `--stage report` fail on exactly the tree they were built
for.

**THERE IS NO ROUND 3.** The budget was fixed in advance so that "keep tuning until it
wins" is unavailable, and it is spent.

Test counts: `data/scripts/tests` is **71** under the training venv (was 55), and
**7 passed + 8 skipped** under `backend/venv` (was 7 + 6) — the two new modules skip
whole there for the usual reason, no torch, which is what shows they add no dependency
to the service-test venv. The five service suites are unchanged at **268**
(questionnaire 18, matching 108, roadmap 30, auth 31, history 81); no file under
`services/` is in this change.

### Reproduction record (DEV-96, 2026-07-31)

The learning curve and the balance-controlled control curve (`learning_curve.py`,
plan Step 2.6). Split like the DEV-91/93/95 records: this ticket edits `nn_model.py`
and `select_by_inner_cv`, which every nested selection in the pipeline goes through,
so almost nothing was supposed to move and "inert" had to be shown rather than argued.

**Unmoved, verified rather than asserted — four ways.**

- **The six Gate-1 metrics**, recomputed by calling `cv_oof_and_stability` and
  `reseeded_stability` **directly** rather than by regenerating `gate1_verdict.json`,
  which this ticket leaves byte-unchanged: `logistic` ECE `0.034099440082920096` /
  stability `0.637516702641587`, `lightgbm` `0.128155228434309` /
  `0.5566450817144618`, `small_nn` `0.06183095636038942` / `0.6153150375167026`,
  reseeded `0.6670161373214101`. All six to the last digit. (Build `X` with
  `dtype=float` as `evaluate_matchers.main()` does — the float32 of
  `train_models.load_data()` moves Gate-1 ECE by ~2.6e-8 and looks like a regression.)
- **The five Gate-2 rows.** `train_models.py` re-run: `model_selection.md` and
  `gate2_winner.json` came back differing **only** in their timestamps, so `gbt_tuned`
  0.892 / 0.040, `logistic_tuned` 0.849 / 0.061, `small_nn` 0.845 / 0.102,
  `two_tower` 0.763 / 0.081 and `residual_matcher` 0.849 / 0.061 all reproduce. This
  is the check that matters most here, because `select_by_inner_cv` gained a
  parameter and four of those five rows are selected through it.
- **Round 1's entire deliverable.** `sweep_variants.py` re-run: `nn_rework.md` and
  `round1_results.json` byte-identical apart from their timestamps — including the
  Ship Floor and C-sensitivity tables, which that script *recomputes* rather than
  reading from its checkpoint.
- **Round 2's report.** `sweep_round2.py --stage report`: `round2_results.json` came
  back **byte-unchanged** and `nn_rework_round2.md` differed only in `Generated:`.
  Worth stating because `full_specification` reads `inspect.signature`, so the new
  `val_size` argument *would* appear in a freshly computed specification —
  `rebuild_report` does not recompute that key, and the recorded one is what the curve
  freezes against.

All regenerated files were reverted rather than committed. `dataset_digest` still
`2bdd5ec99d6a49a2a19c40163cf7a69d560453e3095bc6b4241c6065f18a4b27` throughout, and
`two_tower`'s ordering in `train_models.main()` is untouched — the process-global
torch-RNG hazard is unchanged and still DEV-100's.

**The two additive arguments, and why each is additive.** `NNClassifier(val_size=)`
is an absolute early-stopping split size; the curve's rule
`n_val = max(n_classes, ceil(0.15 * n_train))` cannot go through `val_fraction`,
which is a float handed to `train_test_split` and therefore `ceil(fraction * n)` —
`n_val / n_train` is not guaranteed to round back to the integer it came from. `None`
leaves the `val_fraction` call untouched rather than re-deriving the same number, and
`test_learning_curve.py` pins bit-identity at the default the way
`test_variant_registry.py` does for DEV-93's four arguments. `NNClassifier` also now
records `n_val_`, what the split *actually* held out, so "the rounding landed on the
rule" is checkable from the report rather than only from the code. And
`select_by_inner_cv(..., inner_splits=)` defaults to the pipeline's 3; the curve needs
2 because at n=48 an outer training partition holds two rows of the rarest classes, a
3-fold inner split loses a class, sklearn **warns rather than raises**, and the
estimator then emits fewer probability columns — so the selection metric would read
top-2 indices meaning different careers.

**New, and NOT comparable to any gate number.** `data/training/learning_curve.md` and
`learning_curve_results.json` come from a dedicated **3-fold** protocol on
**subsampled** data with **2** inner selection folds. Gate 1, Gate 2, Round 1 and
Round 2 all use 5 outer and 3 inner folds on all 232 rows. The report says so in a
section that cannot be missed; the Round-2 effect sizes remain the deliverable's
statement of where the neural matcher stands, and this only says how that standing
moves with n.

**Five decisions plan Step 2.6 left open, decided and stated rather than applied
quietly.**

1. **The frozen configuration is a five-member ensemble** —
   `SeedEnsemble(n_members=5, dropout=0.5, weight_decay=1e-2)` — so every neural fit
   on the curve is five fits and the curve measures an *ensemble*. Read from
   `selected_specification` in `round2_results.json` and checked field by field
   against the registry entry, so it cannot quietly measure a later edit of what
   DEV-95 chose. A field the record does not carry is allowed (that is how the new
   `val_size` passes); a field it carries with a different value raises.
2. **The validation rule is an absolute-size argument**, not a per-point fraction —
   see above.
3. **The comparators are NESTED at every point, not frozen**, and that was decided on
   correctness rather than budget. Freezing means either an arbitrary configuration,
   which is no longer the `gbt_tuned` the rest of DEV-23 reports a gap against, or one
   selected on all 232 rows — which would have seen data outside every subsample below
   232, i.e. **Leakage** at four of the five points. It costs 33x on the GBT leg —
   16 grid points × 2 inner folds plus the refit, against one fit.
4. **The comparator legs are computed fresh.** Rounds 1 and 2 could legitimately reuse
   each other's because within a seed the fold partition is a function of the seed
   alone *under the same protocol*; this is a different protocol, so a reused leg
   would be a model scored on a different partition and nothing would have failed.
5. **The subsample is a function of the curve point alone and does not vary with the
   experiment seed.** "The 80 profiles common to both points" is one set only if every
   seed cuts the same subsample. The cost — every number is conditional on ONE
   subsample draw at each point — is disclosed in the report rather than buried.

**Nesting is a property of the construction, not of the arithmetic.** The Delta-gap CI
is computed over the profiles common to n=80 and n=232, which exist only if the
smaller subsample is a subset of the larger. So the subsampler does not apportion
seats independently per point — proportional rounding can hand a class *fewer* seats
at a larger house size (the Alabama paradox) and nesting would break silently. It
fixes one global ordering of the 184 surplus rows (232 minus the floor of 3 per class
times 16 classes) and every point is a **prefix** of it. The ordering key is the
divisor form `(rank + 0.5) / class_surplus`, which cuts at `round(t * surplus)`; the
obvious `(rank + 1) / surplus` cuts at `floor(...)`, over-serves the largest class,
and put the n=80 skew at 4.0 against the **3.7 plan Step 2.6 pre-registered**. With
the divisor key the balance table comes out as the plan states it — skew 1.0 / 3.67 /
4.75 / 8.25 / 9.40 and frontend at 13.8% of n=80 — which is the check that the
construction is the one the plan costed.

**The finding, and it is not the one the ticket was hoping for.**

- **Delta-gap vs `logistic_tuned` = −0.0425**, 95% paired-bootstrap CI
  [−0.0975, +0.0125] over the 80 common profiles. **Flat / inconclusive.**
- **Delta-gap vs `gbt_tuned` = +0.0025**, CI [−0.0800, +0.0850]. **Flat /
  inconclusive.**
- Read as: **at these sizes, more data of this kind is not measurably closing the
  gap** — which is a direct input to DEV-98 and to whether funding more labels is
  worth it. It is *not* evidence the gap is fixed: an interval covering zero covers
  useful narrowing as well as none.
- **The model itself improves steeply with n** — 0.600 top-2 at n=48 to 0.820 at
  n=232 — and so do the comparators (`logistic_tuned` 0.725 → 0.850, `gbt_tuned`
  0.617 → 0.866). More data plainly helps the model; what it does not measurably do is
  help it *faster* than it helps the alternatives, and the report separates those two
  claims because conflating them is the easy misreading.
- **Whether there IS a gap is a different question from whether it moves**, and the
  report answers both: the per-point gap CI excludes zero at 3 of 5 points against
  `logistic_tuned` and 1 of 5 against `gbt_tuned`, and at n=232 the gaps are
  +0.0302 [+0.0026, +0.0595] and +0.0466 [+0.0155, +0.0793]. A reader who took "flat /
  inconclusive" for "no gap" would have it backwards.

**The verdict vocabulary is the plan's two values and not three.** An earlier draft
returned "widening" when the interval excluded zero on the far side. Plan Step 2.6
pre-registers "narrowing" and, for *anything else*, "flat / inconclusive" — a
category invented after seeing the data is not a pre-registered rule. Widening is
recorded on its own key and printed as a disclosure beside the verdict instead. It did
not arise on this data; the mechanism is there so it cannot be quietly absorbed if it
ever does.

**The control curve, and the thing it produced that was not designed.** Two points,
uniform k=4 and k=5 per class (`game-dev`'s 5 labels are the cap), explicitly barred
from carrying trend weight — two points cannot distinguish a trend from a pair of
draws. Its sign comparison against the main curve turned out to carry no information
here, because the main Delta-gap CIs both cover zero, and the report says that rather
than reading a direction out of an interval that does not have one. What it did
produce is an accident worth keeping: **the uniform k=5 point and the main n=80 point
hold the same 80 rows' worth of data at skew 1.00 and 3.67**, so the pair isolates
balance at fixed n. Both gaps are *wider* at the uniform point (+0.1475 vs +0.0900
against logistic, +0.0750 vs +0.0250 against gbt). That is the opposite of the
direction plan Step 2.6 assumed when it warned an observed narrowing might be a
balance effect — though the uniform point also changes the TEST rows, and top-2
agreement on a balanced test set is a harder measurement, so the report states what
the pair does and does not establish rather than banking the result. It is explicitly
marked as carrying no interpretive weight beyond a sanity check, because Step 2.6 bars
control-curve data from carrying any and this pair is made of it.

**Disclosures, counted rather than argued.** The subsample ordering's random
tie-break — two classes with equally many surplus rows produce identical keys —
decided membership at **1 of the 5** main-curve points (n=116, 4 rows contested) and
nothing at the other four. It does not apply to the control curve at all, which takes
a prefix of each class separately. `test_learning_curve.py` requires that where the
count is non-zero the contested rows actually straddle the cut and come from more than
one class, so the number bounds a real choice rather than decorating the report.

**`learning_curve.py --stage report`** re-renders the report from
`learning_curve_results.json` alone — not from the gitignored checkpoint — refitting
nothing, and recomputes every derived key from the per-point per-seed indicators
inside that file so the JSON and the report cannot hold different versions of one
derivation. It was needed for the reason `sweep_round2.py`'s equivalent was: the
long-running process holds the module it loaded at launch, so the prose fixes made
during the run did not reach it and the report was re-rendered afterwards. The run
checkpoints per **(point, seed)** — 35 units — because the nested comparator legs are
where the hours are.

**No calibration number is reported.** The pre-registered reading is about top-2 gaps,
ECE is not part of it, and the Ship Floor's calibration verdict is DEV-95's and stands
unchanged. Nothing here is Qualified, Selected, Servable or Deployable, nothing here
reopens the search budget — **there is still no round 3** — and `MATCHER_MODEL_PATH`
is untouched.

**A code review changed the deliverable, and that is recorded rather than smoothed
over.** It caught four things worth naming. (1) Three claims in the report template
were typed rather than derived — "improves steeply with n", "and so do the
comparators", and the conclusion drawn from the equal-n balance pair — the exact shape
of the failure that bit DEV-91, DEV-93 and DEV-95; all three are now computed, and
"steeply" is earned against Step 2.5's own 0.02 materiality marker rather than
asserted. (2) The growth claim was anchored at **n=48**, the one point the plan
annotates "not a data-size measurement"; every claim is now anchored at the smallest
point above the protocol floor, and the floor point is named wherever it is still
counted. (3) The nested-comparator cost was printed as 16x, the grid size, when
nesting costs grid × inner folds + refit = **33x**; it is computed now. (4) `_report`
interpolated the protocol from this module's live constants, so `--stage report` on a
tree with edited constants would have described a run that never happened; the
protocol keys are carried over from the results file the way `environment` already
was. The review also asked for Step 2.4's "what the CI covers" statement and per-seed
table, which this report had inherited the machinery for and not the disclosure — both
are now in, along with a definition of the `+/-` column.

Test counts: `data/scripts/tests` is **83** under the training venv (was 71), and
**7 passed + 9 skipped** under `backend/venv` (was 7 + 8) — `test_learning_curve.py`
skips whole there for the usual reason, no torch, which is what shows it adds no
dependency to the service-test venv. The five service suites are unchanged at **268**
(questionnaire 18, matching 108, roadmap 30, auth 31, history 81); no file under
`services/` is in this change.

### Reproduction record (DEV-94, 2026-07-31)

The neural serving path (`services/matching/app/services/matcher_nn.py`, plan Step
5.2). **This is the first DEV-23 ticket whose change lands under `services/`, and
nothing in `data/` moved** — no script was run, no artifact regenerated, no gate
recomputed. `dataset_digest` is still
`2bdd5ec99d6a49a2a19c40163cf7a69d560453e3095bc6b4241c6065f18a4b27` because nothing
touched the thing that computes it, and `two_tower`'s ordering in
`train_models.main()` is untouched. This record lives here because it is where the
DEV-23 records live, not because a pipeline script changed.

**Nothing here is Deployable, and nothing here is even a model.** In `CONTEXT.md`'s
terms this ticket delivers the *implementation half* of **Servable** — "an
implementation exists that can execute the artifact at serve time with exact or
tolerance-tested attribution", a property of the serving code. The claim is
deliberately not made flat: the attribution is **tolerance-tested and, on the
synthetic artifact measured below, frequently fails that tolerance**. Whether
Servable holds for the model that ships is settled when a real artifact exists and
is measured, which is DEV-97's. There is still no trained neural artifact, and
`MATCHER_MODEL_PATH` is untouched in `.env.example`, `backend/.env` and
`docker-compose.yml`, so production still runs the formula.

**The environment trap, and how it was resolved.** `backend/venv` had no numpy, and
before this ticket **no module under `services/` imported numpy at all** — so the
moment the dispatch seam imported `matcher_nn`, the matching suite would have failed
to *collect*. numpy was installed into `backend/venv` with `--no-deps`, which is
where `backend/requirements.txt` has declared `numpy>=1.24.0` all along; the venv was
simply out of sync with its own requirements file. That venv is **not** the
hash-pinned training venv, and the separation the digest depends on is intact —
checked rather than asserted: `data/scripts/tests` under `backend/venv` is **7
passed + 9 skipped, unchanged**, because all nine of those modules `importorskip`
torch and/or sklearn as well as numpy, so none of them un-skipped. `pip list` grew
by exactly one package.

**The two decisions plan Step 5.2 left undefined.** Both are now written into the
plan; the second is a finding, not a preference.

1. **IG explains the logit of the mean probability**, `g_c = log(mean_i
   softmax(z_i)_c) / T`, centered across classes — *not* the mean of the members'
   logits that averaging their attributions would explain. The decisive argument is
   in the offline code rather than in the maths: `train_models.apply_temperature` is
   `softmax(log(clip(probs)) / t)`, it consumes **probabilities**, and this model's
   probabilities are the averaged ones. Explaining the mean logit would apply `T`
   somewhere no fit ever put it. **DEV-97 must fit `temperature` on
   ensemble-averaged OOF probabilities and revalidate Gate 1 on
   `SeedEnsemble.predict_proba`** — the same quantity, or the export revalidates a
   model the served explanation does not describe. To be exact about which fit that
   is: the *shipped constant* is `export_model.py`'s deployment temperature —
   `temperature_scale` on pooled OOF from the exact configuration being serialized,
   which ADR 0004 names as one of its two remaining honest uses. It is **not** the
   per-outer-fold cross-fitted temperature ADR 0004 requires for a *reported* ECE;
   that one stays per-fold, and satisfying this instruction must not be read as
   licence to pool the reported number.
2. **"Relative" residual means relative to the delta being explained**, not to the
   attribution mass. This is the strict reading and it was chosen *before* measuring
   which one passed, which turned out to matter a great deal.

**The completeness finding, and the thumbs on the scale, counted.** The integrand is
the gradient along the path; for a ReLU trunk it *jumps* at every activation
breakpoint, so a midpoint Riemann sum is **O(1/m)** and not O(1/m²). Regenerate the
table below with:

```
cd services/matching && ../../backend/venv/Scripts/python tests/ig_diagnostics.py
```

**640 explanations** — 40 profiles x all 16 careers, feature vectors built by
`feature_builder` from the real catalog and question bank, five members at the
shipped trunk shape 84 -> 64 -> 32 -> 16:

| | median | p90 | max |
|---|---|---|---|
| strict residual, `/ abs(delta)` | 1.77e-3 | 7.32e-3 | 3.57 |
| lenient residual, `/ sum(abs(a))` | 9.85e-5 | 3.92e-4 | 1.24e-3 |
| absolute residual | 9.92e-3 | 3.46e-2 | 1.04e-1 |

- **Step counts reached:** 32 x10, 64 x23, 128 x44, 256 x56, 512 x507. So `m`
  doubled at least once in **630 of 640** explanations, and reached the cap in 507.
- **Fall-through: 390 of 640 = 60.9%** of careers emit no model-derived reasons at
  the plan's stated tolerance. Under the lenient denominator it would have been
  approximately none — one number in the whole run exceeds 1e-3.
- **Latency:** ~66 ms per career explained, so ~200 ms per request at `TOP_N = 3`.
  Each `contributions()` call recomputes all 16 classes because centering needs
  them, so the three served careers pay for the same work three times; a per-vector
  cache would cut that to ~66 ms and is deliberately **not** in this change, since
  it puts mutable state on an object shared across request threads.

**The plan's cap of 512 is roughly an order of magnitude short at the strict
reading, and that is left open for a human decision rather than fixed by loosening
the tolerance.** Beating O(1/m) requires locating the breakpoints, which is the
analytic activation-pattern tracking Step 5.2 explicitly rejects — so the trade is
real (accuracy vs latency vs tolerance) and not an implementation defect. The
numbers above come from a **synthetic** artifact with pseudo-random weights, because
no trained one exists until DEV-97.

**How sensitive that 60.9% is, measured rather than guessed** — this is the largest
thumb on the scale in the record, and it was found by the code review rather than by
the author. The weights are `uniform(-1, 1)`; a network trained with
`weight_decay=1e-2` is nowhere near that large. Rerunning at
`--weight-scale 0.3` (same seeds, same profiles):

| weight scale | fell through | strict median | absolute median | reached the cap |
|---|---|---|---|---|
| 1.0 | 390/640 = **60.9%** | 1.77e-3 | 9.92e-3 | 507 |
| 0.3 | 217/640 = **33.9%** | 7.35e-4 | 1.89e-4 | 349 |

So the *direction* is robust — a plain Riemann sum at 512 steps does not reach a
1e-3 strict residual for a large minority of careers at either scale — but **the
magnitude is a property of the fixture, not a prediction about the shipped model**.
Quote the direction, not the percentage. **The real fall-through rate is DEV-97's to
measure.** Two tests pin the shape of the finding so it cannot rot quietly:
`test_completeness_improves_as_the_step_count_rises` (the residual is quadrature
error, so it must fall with `m`) and
`test_a_realistically_shaped_network_does_not_reach_tolerance_at_the_cap` (which
fails if the cap ever *does* become sufficient, forcing a re-read of this record).

**What was verified rather than assumed.** The gradient is checked against central
finite differences of `_explained_logit` (observed agreement 5.8e-9; the committed
test pins the looser 1e-6, which is where a central difference at `h = 1e-6` stops
being trustworthy), which separates "the chain rule through the ensemble mean is
wrong" from "the integral is coarse" — the
quadrature error is easily large enough to hide a small analytic mistake, and
completeness alone would not have caught it. The forward pass is checked against a
hand-worked two-member network whose logits are derivable on paper: at `z = [2, 1]`
the members emit `[1, -1]` and `[2, -2]`, so the served probability is
`(sigmoid(2) + sigmoid(4)) / 2 = 0.9314` and **not** `sigmoid(3) = 0.9526`, which is
what averaging the logits first would give. That fixture is the ensemble decision
made executable.

**The q11-q18 interaction, so no reader is misled.** `reason_builder.py:18`
`QUESTION_PHRASES` covers q1-q10 and is also the iteration set (`:71` — the plan
said `:72`, corrected here). The integrated gradients computed by this ticket cover
all 18 questions correctly, and **16 of the 36 question features are discarded
downstream until DEV-89 lands**. That is unchanged by this ticket and deliberately
not fixed in it; DEV-89 is a blocker of the *merge*, not of the build.

Test counts: the five service suites are **297** (questionnaire 18, matching
**137**, roadmap 30, auth 31, history 81), up from 268 — matching gains the 29 tests
of `tests/test_matcher_nn.py` and **the pre-existing 108 are unchanged**, which is
the evidence that the formula path is inert. `data/scripts/tests` is **83** under
the training venv and **7 passed + 9 skipped** under `backend/venv`, both unmoved.

Four of those 29 exist because the code review found the defects they now pin: two
artifacts that raise `ValueError` out of `np.asarray` (ragged and non-numeric
weights) reached `load_matcher` uncaught and would have taken **service startup
down** instead of falling back to the formula, which is precisely the contract
`load_matcher` exists to keep. The review also caught that the test standing behind
the fall-through finding ran **three** members while the record said five, and that
the record quoted a fall-through percentage without disclosing how hard it depends
on the fixture's weight scale — the table above is the answer to that.

## Pipeline order

```
scrape_job_ads.py
      ↓
extract_skills.py
      ↓
build_rag.py  →  jobs/chroma/

labeling_pipeline.py  →  questions/question_bank_labeled.csv
      ↓
answer_questions_local.py  →  answers/question_bank_answered_local.csv
      ↓
validate_synthetic_output.py  →  reports/
quick_trust_check_local.py    →  reports/
```

---

## Job pipeline

### `scrape_job_ads.py`
Fetches job postings from free APIs (RemoteOK, Jobicy, Remotive, Arbeitnow, and others) and scores each against the 16 canonical fields in `config/field_taxonomy.json`.

```bash
python data/scripts/scrape_job_ads.py
python data/scripts/scrape_job_ads.py --sources remotive arbeitnow
python data/scripts/scrape_job_ads.py --max-per-field 200
```
Output: `jobs/raw/*.json`

### `extract_skills.py`
Reads raw job JSONs and adds a normalized `skills` list to each job via regex patterns + tag passthrough + optional LLM enrichment.

```bash
python data/scripts/extract_skills.py
python data/scripts/extract_skills.py --use-llm     # slower, richer
python data/scripts/extract_skills.py --sources remoteok
```
Output: updates `jobs/raw/*.json` in place.

### `build_rag.py`
Embeds every job posting with `sentence-transformers/all-MiniLM-L6-v2` and stores it in a ChromaDB vector database for RAG retrieval.

```bash
python data/scripts/build_rag.py
python data/scripts/build_rag.py --reset            # rebuild from scratch
python data/scripts/build_rag.py --stats-only
python data/scripts/build_rag.py --query "React TypeScript" --field "Frontend Development"
```
Output: `jobs/chroma/` (gitignored, regenerable)

---

## Labeling pipeline

### `labeling_pipeline.py`
Auto-assigns multi-labels to all questions in `questions/question_bank.csv` using the ontology in `config/label_ontology.json`. Achieves 100% coverage with ~5.5 labels per question on average.

```bash
python data/scripts/labeling_pipeline.py
python data/scripts/labeling_pipeline.py --use-embeddings
python data/scripts/labeling_pipeline.py \
    --input data/questions/question_bank.csv \
    --output data/questions/question_bank_labeled.csv \
    --ontology data/config/label_ontology.json \
    --threshold 0.3
```
Output: `questions/question_bank_labeled.csv`

### `create_visualizations.py`
Generates distribution charts from the labeled question bank.

```bash
python data/scripts/create_visualizations.py
```
Output: `visualizations/*.png`

### `verify_output.py`
Validates the labeled output for coverage and format correctness.

```bash
python data/scripts/verify_output.py
```

---

## Annotation

### `answer_questions_local.py`
Generates synthetic persona answers for all questions using a local Ollama model. Each field is answered by `PERSONAS_PER_FIELD` (default 3) independent personas at distinct temperatures (`PERSONA_TEMPERATURES`) to avoid same-base-model clone effects, mirroring `panel_label_profiles.py`'s panel design. `target_field` is never forced into the model's `predicted_fields` — confirmation is measured honestly, not injected.

```bash
python data/scripts/answer_questions_local.py                  # full run
python data/scripts/answer_questions_local.py --limit 50       # smoke test
python data/scripts/answer_questions_local.py --aggregate-only # recompute the agreement report only
# Requires Ollama running at localhost:11434
```
Output: `answers/question_bank_answered_local.csv`, `reports/question_bank_agreement_report.md`

### `pipeline.py`
Orchestrates the full annotation pipeline end-to-end.

```bash
python data/scripts/pipeline.py
```

---

## Validation & auditing

### `validate_synthetic_output.py`
Checks structural quality of the synthetic annotations: JSON parseability, field-score validity, confidence range, Likert score validity, error rate.

```bash
python data/scripts/validate_synthetic_output.py
```
Output: `reports/synthetic_output_validation_report.md` + `.json`

**Pass criteria:**
- `predicted_fields` JSON valid ≥ 99% of rows
- `field_scores_json` valid ≥ 99% of rows
- Non-empty `error` rows ≤ 1%

### `quick_trust_check_local.py`
Fast trust-check on a small sample — run this before committing to a full annotation run.

```bash
python data/scripts/quick_trust_check_local.py --sample-size 20
python data/scripts/quick_trust_check_local.py --sample-size 20 --skip-model-call  # dry run
python data/scripts/quick_trust_check_local.py --sample-size 20 --model qwen3:14b --timeout-s 90
```
Output: `reports/quick_trust_check_results.csv` + `reports/quick_trust_check_report.md`

**Suggested acceptance rule:** trust pass rate ≥ 90%, JSON/schema validity ≥ 95%, target-field consistency ≥ 85%.

### `audit_question_quality.py`
Audits the question bank for beginner-friendliness and quality flags.

```bash
python data/scripts/audit_question_quality.py
```
Output: `reports/question_bank_beginner_quality_*.{md,csv}`
