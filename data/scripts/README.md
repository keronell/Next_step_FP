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

### Reproduction record (DEV-97, 2026-08-03)

`export_nn_model.py` — the neural sibling of `export_model.py`. **This is the first
ticket in DEV-23 that produces a trained neural artifact**, and therefore the first
that can make the claims the earlier ones had to defer.

```
data/venv-training/bin/python data/scripts/export_nn_model.py
```

Nothing that gates anything was re-run: no sweep, no Gate-2 re-baseline, no
relabeling. `dataset_digest` is still
`2bdd5ec99d6a49a2a19c40163cf7a69d560453e3095bc6b4241c6065f18a4b27`, verified by the
exporter itself before it will proceed, and `two_tower`'s ordering in
`train_models.main()` is untouched because nothing here reaches it.

**What state this reaches, and the vocabulary problem it exposes.** `CONTEXT.md`'s
four states are distinct and none implies an earlier one. This ticket delivers
**Servable** for real (an artifact now exists and the serving code executes it with
measured attribution) and performs the post-export revalidation **Deployable**
requires — but it does **not** reach Deployable, and saying otherwise would be the
exact four-state conflation `CONTEXT.md` exists to prevent:

> **Deployable**: Qualified, Servable, and revalidated against the Gate 1 thresholds
> *after* export in its exact shipped configuration.
> **Qualified**: Cleared Gate 1 — calibrated and stable.

`matcher_nn_v1` is stable and **not calibrated**, so it is not Qualified, so it is
not Deployable. **ADR 0002 splits the ship *floor*; it does not split the *state*.**
The two documents are in genuine tension — ADR 0002 says a model failing ECE "may
still ship as the *ranking* source", which describes something the four states have
no name for. This record does not invent one, and does not stretch "Deployable" to
cover it. **Reconciling that vocabulary belongs to DEV-98**, which writes the
decision document; flagged here rather than quietly resolved.

The accurate sentence: *`matcher_nn_v1` may serve the ranking under ADR 0002's
mitigation, with displayed percentages falling back to the formula's.*

`MATCHER_MODEL_PATH` is unchanged everywhere and **production still runs the
formula**. Precisely: it is blank in `.env.example` and defaults to blank in
`docker-compose.yml`; `backend/.env:23` still points at the stale
`matcher_logistic_v1.json`, which is untouched by this ticket and never reaches the
services anyway, because compose reads the root `.env`. Flipping the live one is
DEV-99 and reserved for human approval.

**The configuration is read, not retyped.** `selected_specification` in
`round2_results.json` is generated from `inspect.signature`, and the exporter
rebuilds from it. The reconstruction is then *proved* faithful rather than argued:
revalidating reproduced DEV-95's recorded ship floor at **max drift exactly 0** on
both numbers. That is what rules out a silently changed default — a signature audit
would not have. One parameter, `val_size`, postdates the record (DEV-96 added it);
it is reported at run time rather than absorbed silently, and the zero drift is the
evidence it is inert.

#### The split ship floor, and why the exporter does not simply refuse

| half | measured | floor | verdict |
|---|---|---|---|
| top-2 stability (**hard**, ADR 0002) | **0.7345667591736047** | >= 0.60 | **CLEARS** |
| pooled OOF ECE (**mitigable**, ADR 0002) | **0.13922660469462908** | <= 0.10 | **FAILS** |

Both reproduce DEV-95 to the last digit. DEV-97's acceptance criterion says export
"refuses to write when it fails"; taken flat that refuses to write the model the
project has already decided to ship, and the ticket's own scope-note comment says
so. So the exporter distinguishes the halves: it **refuses on stability**, which
ADR 0002 gives no mitigation, and on **ECE it writes and records the failure**.

The mitigation is carried where a consumer cannot miss it. The artifact has no bare
`deployable: true` to misread — `deployment.status` is the string `"ranking_only"`,
`deployment.match_percent` reads `FALL BACK TO THE FORMULA`, and a fourth entry
joins `caveats`, which travel inside the artifact to the recommendations response,
the persisted history and the results UI. **This model may serve the ranking; its
percentages are not calibrated and must not be displayed as if they were.**

**The deployment temperature is 0.80**, fitted by `fit_temperature` on
ensemble-averaged OOF — `SeedEnsemble.predict_proba`, the mean of the members'
probabilities, which is the quantity DEV-94's attribution takes the logit of. It is
the same-pool fit `train_models.temperature_scale`'s docstring still calls honest
for choosing one shipped constant, and it is **not** ADR 0004's per-outer-fold
cross-fitted temperature, which still governs any *reported* ECE. (ADR 0004 itself
enumerates no "two honest uses" — that phrasing belongs to the `temperature_scale`
docstring, and the DEV-94 record above miscites it the same way. Left as written
there, corrected here.) Note the direction: the linear artifact's 1.05 softens, this one
**sharpens**. Ranking is unaffected either way (temperature scaling is monotone
within a row); only the displayed percentage moves, and for this model the displayed
percentage is the thing the ECE failure says not to trust.

#### The parity work found a real defect, and it was not a small one

Torch trains in float32; the serving path computes in float64. Over the complete
232-row dataset, per member and for the ensemble average, the naive export diverged
by up to **1.03e-2** in probability — a full percentage point of `matchPercent`,
which is exactly the "the served model is not the model that was evaluated" failure
DEV-97 exists to prevent.

The cause is not the network. Feeding the *same* standardized matrix to both
runtimes agrees to **1.6e-6**, so the forward pass was always fine. It is the
standardization, and the intuitive diagnosis of it is wrong:

- `NNClassifier` uses `scale_ = X.std(axis=0) + 1e-8`, so a column that never varied
  gets a scale of ~1e-8 instead of a zero it could branch on. Five of the 84
  features are exactly constant on this dataset (`fullstack_skill`, `mobile_skill`,
  `game-dev_skill`, `technical-writer_skill`, `software-architect_skill`).
- The tempting conclusion is that such a column standardizes to 0.0 and is inert.
  **It does not.** `mean_` is the float32 mean of 232 values and accumulates
  rounding: `game-dev_skill` is 0.8 in every row, `float32(0.8) = 0.800000011920929`,
  and the computed mean is `0.8000001311302185`. The residual is -1.19e-7 over a
  scale of 1.29e-7, so **training fed the network a constant -0.9226 on that input**
  and the network absorbed it as an extra bias.
- Serving cannot reproduce that by copying the numbers across: in float64 the same
  expression gives **-1.0149**, a different constant. An intermediate attempt to
  emit `scale = 0.0` was also wrong, and measurably so — it fed 0.0 where training
  fed -0.9226 and made the divergence *worse* (9.8e-2).

The fix is exact rather than compensatory: each constant column's fixed contribution
is folded into the first layer's bias (`bias += W[:, j] * v_j`), its weight column
zeroed, and its scale exported as 0.0 — the case `matcher_nn` already branches on.
The composed function is identical to training's for every input, and the ~1e7
amplification leaves the serving path instead of being cancelled inside it.

| export | max abs probability divergence, complete dataset |
|---|---|
| naive (copy `mean_`/`scale_`) | 1.03e-2 |
| `scale = 0.0` for constant columns | 9.80e-2 |
| **folded into the bias (shipped)** | **3.15e-7** |

Parity is asserted **per member and for the ensemble**, because the average is
order-invariant and five members mapped to the wrong seeds would produce a perfectly
plausible one. `test_member_order_is_not_scrambled` therefore also asserts each
serialized member *disagrees* with the other four; without that half a permutation
passes every other check in the file.

**Thumbs on the scale, counted.**

- **Tolerance `1e-5`**, chosen from what the runtimes can differ by rather than from
  what passed: float32 eps is ~1.2e-7 and three layers of accumulation put the floor
  near 1e-6. The measured maximum across every check is 4.7e-7, and the defect it
  had to catch was 1.03e-2 — three orders of magnitude above the bar on one side,
  twenty-odd below it on the other.
- **Rows actually compared: all 232**, times 16 careers, times 5 members
  individually plus the ensemble — not a sample. Plus 200 randomized vectors. Logits
  are compared per member on the same 232 rows, at a *relative* bar (they are
  unbounded, so an absolute one would be a weaker claim on rows with large logits).
- **The randomized vectors hold the five constant columns at their training value.**
  Varying them would not compare the runtimes; it would compare two extrapolations
  of a feature the model has no information about, where torch's ~1e7 slope makes
  any disagreement meaningless. That is a deliberate exclusion and it is the one
  place the randomized test is narrower than it looks.
- **The ECE failure is reported in this record before the parity work and in the
  same table as the stability pass**, not appended as a footnote.

**Where the parity tests live, and why.** In `data/scripts/tests/`, under the
training venv — the only environment that can hold torch *and* import the real
`NeuralMatcher`. Reimplementing the numpy forward pass under `data/scripts/` to dodge
the import was rejected: it would compare two copies of the same code and pass while
proving nothing. The import needs one disclosed shim — `matcher_nn` reaches
`common.config` and therefore `pydantic_settings`, which the hash-pinned training
venv does not have and must not gain, so `common.config` is stubbed to a log level.
**The code under test is byte-identical**; only a logging dependency it never
exercises is replaced. Nothing was installed into `data/venv-training`.

#### The linear path had no parity check. It does now.

Checked rather than assumed: `services/matching/tests/test_matching_with_model.py`
says "shape parity" but means the *response* shape, and drives `MatcherModel` from
hand-built artifacts with round coefficients. Nothing compared the fitted sklearn
estimator against the stdlib reimplementation that serves it — which matters
because that reimplementation is pure `math`, so a divergence would announce itself
as nothing at all. `data/scripts/tests/test_export_model.py` adds it: complete
dataset plus randomized vectors, max divergence ~1e-15 against a `1e-9` bar.

One finding fell out of it. `MatcherModel` works in logit space and never clips,
while `train_models.apply_temperature` works in probability space and must
`clip(probs, 1e-9, 1.0)` to take a log. For a linear model these are the same
function wherever the clip does not bind — but off-distribution vectors drive
sklearn's probabilities to ~1e-47, where it binds hard and the two references
disagree by 4.0e-8. The reference is therefore the unclipped logit-space quantity,
with a test pinning that it agrees with the probability-space one on the real data,
so the choice is not a quiet redefinition of what `temperature` means. This is a
property of the two *reference* implementations, not a defect in serving.

#### The IG fall-through rate on the model that actually ships

DEV-94 could only measure a synthetic artifact and said so, predicting that a
`weight_decay=1e-2` network would be nowhere near `uniform(-1, 1)` and that the real
rate was DEV-97's to measure. It is measured now:

```
cd services/matching && ../../backend/venv/Scripts/python tests/ig_diagnostics.py \
    --artifact ../../data/models/matcher_nn_v1.json
```

| artifact | explanations | fell through | strict median | reached the 512 cap |
|---|---|---|---|---|
| real `matcher_nn_v1` | 640 | **75 = 11.7%** | 5.17e-4 | 146 |
| real `matcher_nn_v1`, 100 profiles | 1600 | **167 = 10.4%** | 5.13e-4 | 350 |
| synthetic, weight scale 1.0 (DEV-94) | 640 | 390 = 60.9% | 1.77e-3 | 507 |
| synthetic, weight scale 0.3 (DEV-94) | 640 | 217 = 33.9% | 7.35e-4 | 349 |

**DEV-94's prediction was right and its numbers were pessimistic by roughly a factor
of five.** The real rate is ~10-12%, stable across the two sample sizes, and the
strict median residual now sits *under* the 1e-3 tolerance rather than above it. The
synthetic rows still reproduce exactly, which is what confirms the change to
`ig_diagnostics.py` measures the artifact rather than moving the goalposts.

**This does not settle the open cap/tolerance decision, and it is not this ticket's
to settle** — it is an accuracy/latency/tolerance trade reserved for a human
(todo.txt section 2, plan Step 5.2). What it does is resize it: "a large minority of
careers emit no model-derived reasons" is no longer the right description of the
shipped model; "about one in nine" is. Whether that is acceptable, or worth buying
down by raising the cap or by changing what "relative" divides by, is unchanged as a
question.

**The q11-q18 interaction, so no reader is misled.** `reason_builder.py:18` defines
`QUESTION_PHRASES` for q1-q10 and that dict is also the iteration set (`:71`). The
attributions this artifact produces cover all 18 questions correctly and **16 of the
36 question features are discarded downstream until DEV-89 lands**. Unchanged by this
ticket and deliberately not fixed in it: DEV-89 is a blocker of the *merge*, not of
the build.

**Test counts.** The five service suites go **297 -> 298** (questionnaire 18,
matching **138**, roadmap 30, auth 31, history 81). This ticket adds no service
*code*, and the **pre-existing 137 matching tests are unchanged**, which is what
shows the formula path is still inert. The one addition is
`test_the_shipped_neural_artifacts_caveats_reach_the_recommendations`: the existing
caveat-propagation tests drive a stub with hand-set caveats, so nothing carried the
real artifact's own caveats to a response. It skips if the artifact is absent.

`data/scripts/tests` goes **83 -> 111** under the training venv: 23 in
`test_export_nn_model.py` (the split-floor branch, the reconstruction, the fold, the
parity family, the artifact round-trip through `load_matcher`) and 5 in
`test_export_model.py` (the linear parity check that was owed). Under `backend/venv`
it is **7 passed + 11 skipped**, up from 7 + 9: the two new modules skip whole
because they `importorskip` torch and sklearn. **The 7 passed did not move**, which
is what shows no module un-skipped and the training/serving venv separation is
intact.

**What the code review changed**, since none of it was polish. It caught that
`main()` reconstructed the shipping estimator a *second* time by hand, bypassing
every guard `build_estimator` performs — so the validated configuration was not the
one that got serialized; `factory()` now goes through `build_estimator`. It caught
that `constant_feature_mask` tested constancy in **float64** while the pathology is
triggered by `std` collapsing in **float32**, leaving a column that varies only
below float32 resolution unfolded and pathological. It caught that
`training_standardized` widened `scale` before dividing, so it was not quite the
float32 expression it claimed to reproduce. It caught that the new
`--artifact` branch of `ig_diagnostics.py` read `members`/`temperature`, which are
not on the `Matcher` protocol, so a linear artifact would load and then crash. And
on the spec axis it caught that parity was asserted on probabilities only, when the
acceptance criterion says "logits **and** probabilities" — softmax is invariant to a
shared additive shift, so probability parity alone would miss a uniform logit drift,
and logits are the quantity the attribution is expressed in. All five are fixed and
the artifact was re-exported; the two dtype fixes moved the serialized biases, which
is why `test_the_shipped_artifact_is_the_model_that_was_evaluated` failed until it
was.

### Reproduction record (DEV-98, 2026-08-03)

The decision document — `docs/dev-23-nn-decision.md` — plus the plan's Step 4 and
Step 6 writeups, the vocabulary fix, and one new script. **Nothing was retrained,
re-exported, re-swept or re-tuned**; `dataset_digest` is untouched at
`2bdd5ec99d6a49a2a19c40163cf7a69d560453e3095bc6b4241c6065f18a4b27` and every figure in
the document is read back from `data/training/*.json`, the two artifacts, or the
measurement below.

#### The one number in this deliverable that had never been computed

Every report in this tree, ADR 0001, plan Step 4.1, `evaluate_matchers.py`'s docstring
and — the reason it matters — the `caveats` list **inside both exported artifacts**
carry the claim that the panel's stage-2 vote "follows the answer key derived from
`careers.json` bonuses ~94% of the time it speaks". Nothing computed it. It is easy to
assume `panel_label_profiles.py` does, because it writes a superficially similar
formula-vs-panel figure into `synthetic_agreement_report.md`; that number is 52.2% and
answers a different question.

```bash
data/venv-training/bin/python data/scripts/measure_circularity.py
```

| reading | measured | what it is |
|---|---|---|
| stage-2 top-1 inside the stage-1 shortlist | 678 / 678 = **100.0%** | **structural, not evidence** — the prompt permits nothing else |
| stage-2 top-1 follows the tie-breaker key (any bonus) | 615 / 651 = **94.5%** | the quoted "~94% of the time it speaks" |
| the same, primary (+3) rules only | 516 / 651 = **79.3%** | the strict reading, materially weaker |
| the consensus **label** follows the key | 206 / 217 = **94.9%** | carries the vote-level rate to what models train on |

**The claim reproduces.** The script recomputes the >= 2/3 consensus filter from the
raw vote log rather than reading `silver_labels.parquet`, and gets **232** profiles —
so the vote log and the recorded dataset still describe one dataset, and the 94.5% is
measured over exactly the votes that produced the shipped labels.

`tests/test_measure_circularity.py` (7 tests) then pins **the shipped caveat text**
against the measurement, parsing the rate out of both artifacts rather than
string-matching a sentence `build_caveats` owns. Regenerating the labels now breaks the
build instead of quietly leaving every artifact asserting a stale rate to users.

The stage-1 and answer-key logic is **imported** from `panel_label_profiles`, not
reimplemented — a reimplementation would compare two copies of the same logic and agree
while proving nothing, the same reasoning that put the DEV-97 parity tests in the
training venv. That import needs one disclosed shim: the module imports `requests` and
`tqdm` for the Ollama call, which the hash-pinned training venv does not have and must
not gain, so both are stubbed. Nothing reached from here touches either, and the
imported code is byte-identical. **Nothing was installed into `data/venv-training`.**

#### Two recorded figures were wrong, and both are corrected

- **Fleiss κ.** Plan Step 4.1 and the DEV-98 ticket both say "κ ≈ 0.88–0.92". That
  matches no run in this tree. `synthetic_agreement_report.md` records **0.857** for the
  shipped `panel-v2.1.0` labels (pairwise Cohen's 0.843 / 0.853 / 0.875); 0.930 was the
  rejected clone-persona `panel-v1.0.1` and 0.864 was `panel-v1.1.0`. Corrected in the
  plan and in the decision document. The caveat's *direction* is unchanged — a κ near
  1.0 would be a red flag for persona non-independence, not a quality guarantee.
- **Which `logistic` clears the ECE floor.** ADR 0002 says the floor "is known
  achievable — `logistic_tuned` clears both (ECE 0.0341, stability 0.6375)". Those
  numbers are `gate1_verdict.json`'s **`logistic`** row, the fixed `C = 1.0`
  configuration `matcher_logistic_v2.json` actually serialises. Gate 2's
  `logistic_tuned` selects `C` per outer fold (4.0, 4.0, 4.0, 0.05, 0.25) and its *raw*
  ECE is **0.103**, which would fail the same floor. Both are honest and they are
  different configurations. **Corrected in `docs/adr/0002` itself**, in the
  "Observed on..." style ADRs 0003 and 0004 already use — describing the error only in
  a downstream document would have left the ADR still asserting it. The decision stands;
  the claim survives the correction and is if anything stronger, since the floor turns
  out to be achievable by the exact configuration that ships rather than by a nested
  protocol with no artifact.

  **This propagates to `Incumbent`.** `CONTEXT.md` defines it against **Deployable**, and
  `logistic_tuned` — having no single configuration and no artifact — cannot be
  Deployable. The Incumbent is therefore `matcher_logistic_v2.json`, the exported fixed
  `C = 1.0` artifact. The consequence is a real limitation and the decision document
  carries it: **every effect size in this deliverable is measured against
  `logistic_tuned`, which is not the model that would actually be replaced**, and no
  round measured the neural matcher against the artifact's configuration. The available
  (unpaired, different-protocol) evidence points to that gap being *wider* — `C = 1.0`
  scores top-2 0.8707 against `logistic_tuned`'s nested 0.849 — so it is stated as a
  direction and **no δ is computed from it**.

#### The vocabulary gap DEV-97 handed here, and how it is closed

`CONTEXT.md` defined **Deployable** as "Qualified, Servable, and revalidated" and
**Qualified** as "cleared Gate 1 — calibrated *and* stable". `matcher_nn_v1` is stable
and **not** calibrated, so it is neither. But ADR 0002 says a model failing the ECE half
"may still ship as the *ranking* source" — a real, intended condition with no name,
because **ADR 0002 splits the ship *floor*, not the *state***.

Resolved by **adding one state**, `Ranking-Deployable`, rather than amending `Qualified`
or `Deployable`: amending either would retroactively change what every earlier record
meant by those words, which is the four-state conflation `CONTEXT.md` exists to prevent.
Its machine-readable form is the `deployment.status: "ranking_only"` string the artifact
already carries, so the vocabulary term and the artifact field are one concept. It is
explicitly **not** a weaker `Deployable`, and it can never make a model the `Incumbent`
(defined against `Deployable`).

The only deployability sentence the document asserts: *`matcher_nn_v1` is
Ranking-Deployable — it may serve the ranking under ADR 0002's mitigation, with
displayed percentages falling back to the formula's.*

#### Thumbs on the scale, counted

The document's own §9 counts eight; the three worth repeating here because they are
about **this** ticket's honesty rather than the training runs':

- **The ECE failure is reported before the stability pass** in every table it appears
  in, and in the state sentence above — not appended as a footnote to a headline pass.
- **Effect sizes quoted without a CI are named rather than left to be noticed**: the
  ADR 0003 substitution cost (+0.0280 mean inner-CV, worst contest +0.0702), the
  ensemble attributions (D5 − D6 = +0.0237, C3 − V0 = +0.0353), and every Gate-1 /
  Gate-2 figure, which are single-partition point estimates. All are on the *selection*
  metric, not the reported one.
- **Which comparisons are paired is stated per comparison.** The §4 effect sizes, the
  Round-1-vs-Round-2 δ and every learning-curve gap are exactly paired. The
  artifact-vs-artifact and Gate-1 tables share a protocol and partition but differ in
  estimator, so they size a change rather than transfer a verdict. The control curve's
  two points share no profiles, so no CI is computed across them.

#### Scope, stated because the temptation ran the other way

`MATCHER_MODEL_PATH` is **unchanged everywhere** — blank in `.env.example`, blank by
default in `docker-compose.yml`, and `backend/.env:23` still points at the stale
6-career `features-v1` `matcher_logistic_v1.json`, which is correctly refused on load
and never reaches the services anyway because compose reads the root `.env`. Production
runs the formula. Flipping it is DEV-99 and is reserved for human approval; this
document is the input to that approval, not the approval.

No sweep was re-run (**there is no Round 3**), no model retrained, no artifact
re-exported, and `matcher_nn.py`'s attribution maths is untouched. DEV-89 (q11–q18
reason rendering) is untouched and remains a blocker of the serving *merge*; the
document names it where a reader would otherwise be misled about explainability
coverage.

**What the code review changed**, since none of it was polish. **Both axes
independently caught the same hard error**: the decision document called the Incumbent
`logistic_tuned`, which is the exact `logistic`-vs-`logistic_tuned` conflation the same
document was written to correct — it committed the error it documents, and
`CONTEXT.md`'s definition of `Incumbent` (against `Deployable`) makes it a vocabulary
violation rather than a wording slip. Fixed above, and it grew a real disclosure out of
it: the comparator every δ uses is not the model that would be replaced. The Standards
axis additionally caught that ADR 0002 was left carrying the wrong attribution while the
plan's κ error had been corrected in place — an asymmetry with no defence — that a test
docstring cited the wrong populations (678 / 226 rather than the 651 / 217 the rates are
actually over), and that the record's venv paths broke the README's own POSIX
convention. It also flagged `measure()` as one loop shape written twice and a 13-key
string-indexed `stats` dict; both are gone — the two populations now run through a single
`tally()` over a `Tally` dataclass, which is what makes it structurally impossible for
the vote-level and label-level readings to drift apart by one acquiring a filter the
other lacks. Every number reproduces byte-for-byte after the refactor. Three unused
generality hooks (`measure(careers=...)`, `load_votes(prompt_version=...)`, and the
matching CLI flag) were deleted rather than kept for a caller that does not exist.

One correction the review did not raise and this record owes anyway: the decision
document quoted DEV-94's **~200 ms/request** IG latency as though it described the
shipped model. It does not — that was the synthetic fixture, which hit the 512-step cap
in 507 of 640 explanations against the real artifact's 146. Cost is roughly linear in
the steps actually taken, so the real figure is materially lower and **nobody has
measured it**. It is now labelled an upper bound inherited from a harder fixture.

**Test counts.** The five service suites are **unchanged at 298** (questionnaire 18,
matching 138, roadmap 30, auth 31, history 81) — this ticket adds no service code and
touches no served output. `data/scripts/tests` goes **111 → 118** under the training
venv (the 7 new circularity tests). Under `backend/venv` it is **7 passed + 12 skipped**,
up from 7 + 11: the new module skips whole because `panel_label_profiles` needs pandas.
**The 7 passed did not move**, which is what shows the training/serving venv separation
is intact and nothing un-skipped.

### Reproduction record (DEV-99, 2026-08-03)

Flip readiness for `MATCHER_MODEL_PATH`. **The flag is untouched** — blank in
`.env.example:15`, blank by default in `docker-compose.yml:56`, and blank in the
repo-root `.env` compose actually interpolates. Production runs the formula. DEV-99 is
human-gated (`ready-for-human`), its Jira status is unchanged, and nothing here approves
anything. Nothing was retrained, re-exported or re-swept; `dataset_digest` is untouched
at `2bdd5ec99d6a49a2a19c40163cf7a69d560453e3095bc6b4241c6065f18a4b27`.

Deliverable: `docs/dev-23-flip-readiness.md`, `services/matching/tests/test_flip_readiness.py`,
`services/matching/tests/flip_diagnostics.py`, plus an "Observed on…" note in ADR 0002
and a pointer at the end of the decision document. Neither of the latter two changes any
existing claim or number.

#### The finding: ADR 0002's mitigation is documented in three places and built in none

The artifact `matcher_nn_v1.json` carries `deployment.status: "ranking_only"`,
`deployment.match_percent: "FALL BACK TO THE FORMULA"`, and a caveat saying its
percentages are uncalibrated. `CONTEXT.md`'s **Ranking-Deployable** and ADR 0002 both
define the mitigation as displayed percentages falling back to the formula's. **No
serving code reads any of it:**

- `services/matching/app/services/matcher.py` declares the `Matcher` protocol with
  `feature_names`, `version`, `caveats`, `predict_proba`, `contributions` — and **no
  `deployment` member**, so both implementations discard the block at load.
- `matching_service.py:323` sets `"matchPercent": round(probs[cid] * 100)` on the model
  path with no branch. The formula's percentage is computed at `:399`, inside
  `_match_formula`, which does not run when the model scores.
- `deployment`, `ranking_only` and `match_percent` appear nowhere in `services/` or
  `frontend/src/` outside the artifact JSON.

So flipping the flag today would display exactly the uncalibrated percentages the
artifact's own caveat forbids. The decision document's *"switching would not improve the
displayed percentages — it would leave them exactly as they are today, by design"* is
true of the design and **false of the code**. This resizes DEV-99: its premise was
"approve, then flip", and the flip is not yet the thing ADR 0002 authorised.

**Not fixed here, deliberately.** The cheap reading ("one branch") is wrong — the fix
needs the per-career formula score for careers `_match_formula` never returns (it returns
only its own `TOP_N`), and it raises a question ADR 0002 does not answer: substituted
percentages are **not monotonic** in the model's ranking, so the UI would print a lower
percentage above a higher one. That is a product decision and possibly an ADR amendment,
so it is surfaced rather than chosen. The gap is pinned by two `xfail(strict=True)`
tests that turn into a loud `XPASS` failure when the mitigation lands; they deliberately
do **not** assert today's behaviour as correct, which would turn the defect into a spec.

#### Two measurements, computed rather than quoted

`cd services/matching && ../../backend/venv/Scripts/python tests/flip_diagnostics.py`
(seed 20260803, fixed so the record reproduces):

Displayed top-1 `matchPercent`, 200 answer sets over the full 18-question bank:

| scorer | mean | min | max |
|---|---|---|---|
| formula (what ADR 0002 says to display) | 73.3 | 60 | 85 |
| `matcher_nn_v1` (what is displayed today) | **58.0** | 26 | 85 |
| `matcher_logistic_v2` | 76.4 | 35 | 99 |

**DEV-89 sized on the artifact that would ship**, 300 explanations, positive attribution
only (negative mass is unrenderable for every question, in the bank or out, so counting
it would inflate the gap):

| reading | value |
|---|---|
| by feature **count** (the usual figure) | 16 of 36 discarded = **44.4%** |
| by attribution **mass**, renderable mean | 0.293 (median 0.158) |
| by attribution **mass**, **discarded** mean | **0.707** |
| explanations losing the *majority* of their question mass | **248 / 300 = 82.7%** |

**About 71% of the question-feature attribution the model produces is discarded before
it reaches a sentence, not 44%.** This is the quantitative form of DEV-98's qualitative
prediction that q11–q18 are "precisely the features a learned model has most reason to
lean on" — they carry zero questionnaire weight and signal only through per-option
bonuses. DEV-89 remains its own ticket on its own branch off `main`; nothing here
touches `reason_builder.py`.

**Disclosure, counted rather than argued.** Candidates come from
`tests/conftest.make_candidates()`, whose RAG signals are canned — `chromadb` is absent
from `backend/venv`, so the real store cannot be driven from there. Two things ride on
that and only one is testable from here, so the script measures the one it can:

| seed | formula top-1 | `matcher_nn_v1` top-1 | gap |
|---|---|---|---|
| 1 | 73.6 | 59.1 | 14.6 |
| 2 | 73.8 | 61.2 | 12.6 |
| 3 | 73.6 | 56.9 | 16.7 |
| 4 | 72.8 | 57.9 | 14.9 |
| **across seeds** | | | **mean 14.7, min 12.6, max 16.7** |

against the headline seed's 15.3 — so **the answer-set draw is not doing the work**. The
canned RAG signals stay a disclosure rather than a measurement: they cannot be varied
without `chromadb`, and what they would have to shift is a ~15-point gap holding in the
same direction across five independent draws. Ranking-agreement rates between scorers
*are* fixture-dependent (the canned semantic similarities dominate the formula), so the
script does not compute them and nothing in this deliverable quotes them.

#### The three mechanical criteria, verified by running rather than reading

All four load-failure modes (stale `features-v1` artifact, missing file, unknown
`model_type`, feature-version mismatch) drive the real `main.lifespan` to `None` and then
serve a response **identical to the no-model one** — not merely "a fallback engaged",
since a fallback leaving `model_version` or `model_caveats` stamped would pass the weaker
check while telling a user their result came from a model that never scored it. Startup
logs the loaded version for both artifacts. Rollback is proved in a single process with no
module reload: only the setting changes, which is what makes "no redeploy of code" true.

**The rollback limit, which is not a defect but is not restored either:**
`model_version`/`model_caveats` are embedded per recommendation and persisted verbatim
(`SubmissionHistoryItem.recommendations: list[dict]`). Clearing the flag changes what
**new** submissions are scored with and rewrites nothing already stored. And
`matchPercent` reaches the UI in two places — `Results.jsx:96` and `History.jsx:187` —
while `model_caveats` renders in **one**, so a persisted uncalibrated percentage is
re-displayed later with no caveat beside it.

#### One repo-wide wording correction

Several docs say `backend/.env`'s `MATCHER_MODEL_PATH` "never reaches the services".
Measured with `docker compose config`, it reaches **two** of them — `auth` and `roadmap`,
via `env_file: ./backend/.env` — which ignore it, because only
`services/matching/app/main.py:44` reads `matcher_model_path` even though
`common/config.py:22` defines it for every service. For `matching`, compose's
`environment:` key overrides `env_file:` and resolves to `''`. The conclusion the docs
draw is right — **it never reaches the service that uses it** — but the literal sentence
is not, and the stale artifact is refused on load in any case.

**Test counts.** Service suites **298 → 307 passed + 2 xfailed** (matching 138 → 146 + 2,
questionnaire 18 → 19; roadmap 30, auth 31, history 81 unchanged). The 2 xfails are the
mitigation gap, expected-to-fail by design. `data/scripts/tests` is **unchanged**: 118
under the training venv, 7 passed + 12 skipped under `backend/venv`. **No served output
moved** — the 138 pre-existing matching tests all still pass, and every new test either
adds coverage or asserts the formula path is what it was.

**What the code review changed**, since none of it was polish:

- **The Spec axis caught the second `xfail` resting on a false invariant.** It compared
  `matchPercent` against `round(score * 100)`, but `score` is `round(prob, 3)` while
  `matchPercent` is `round(prob * 100)` — the two already disagree for **33 of 600**
  recommendations (5.5%) purely by rounding. The test XFAILed for partly the wrong
  reason, and a future `XPASS` could have been rounding rather than the mitigation. It
  now compares against the model's **unrounded** probability. The same overstatement
  ("today `matchPercent == round(score * 100)` on both paths") is corrected in the
  document, where that test was cited as though it asserted a global invariant rather
  than one rec of one fixture.
- **The artifact-side assertion was inside the strict `xfail`.** An exporter that
  stopped emitting `deployment` would have raised `KeyError`, been recorded as the
  expected failure, and left the regression green. Split into a plain passing test.
- **The Standards axis caught this record's own first draft asserting that `deployment`
  / `ranking_only` "appear nowhere in `services/`"** — falsified by the test file added
  in the same diff. Rescoped to serving code, and the correction is left visible,
  because it is the same right-conclusion-from-a-false-premise shape as the compose
  wording below.
- **Asymmetric correction, a failure this project has already recorded once** (DEV-98's
  review: "ADR 0002 was left carrying the wrong attribution while the plan's κ error had
  been corrected in place — an asymmetry with no defence"). The compose-scope wording was
  corrected here and left standing in the *living* docs. `CLAUDE.md` and `README.md` are
  now fixed in place; the historical records (DEV-98's above, and the decision document's
  §10) keep their wording and carry a pointer, which is the house treatment for a record
  versus a live instruction.
- **The Spec axis named the cheapest remaining coverage gap** and it is now closed:
  `test_the_real_artifacts_caveats_survive_the_response_and_reach_persistence` in
  questionnaire-service carries the **real** artifact's caveat strings through the
  response-level derivation and into the persisted payload. DEV-97's test stopped at
  `/internal/match`; questionnaire's own used hand-written strings.
- Two unused CLI flags on `flip_diagnostics.py` were deleted (Speculative Generality —
  the same call DEV-98's review made about three hooks there), and the seed-sensitivity
  block replaced an argued disclosure with a counted one.

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

### `measure_circularity.py`
Measures how far the silver labels reproduce the `careers.json` answer key — the
"~94% of the time it speaks" claim that every report, ADR 0001, and the `caveats`
inside both exported artifacts assert. Reads the raw vote log; imports
`panel_label_profiles`'s own stage-1 shortlist and option→career key rather than
reimplementing them. Needs the **training** venv (pandas), and installs nothing.

```bash
data/venv-training/bin/python data/scripts/measure_circularity.py
data/venv-training/bin/python data/scripts/measure_circularity.py --json
```
Output: stdout only. Four readings — see the DEV-98 reproduction record above for what
each one answers, and why shortlist containment is structural rather than evidence.
`tests/test_measure_circularity.py` pins both artifacts' caveat text against it, so
regenerating the labels fails the build rather than leaving a stale rate in front of
users.
