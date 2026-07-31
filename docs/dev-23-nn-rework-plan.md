# DEV-23 — Neural Matcher Rework: Execution Plan

**Branch:** `dev-23` (from `main`)
**Status:** PLAN rev 3 — incorporates external review of rev 2 and the
requirement clarification that reframed it; ready to execute
**Written:** 2026-07-26 · **Revised:** 2026-07-27

## What this ticket is

DEV-23 asks to replace the weighted formula with a neural network as the
production-serving path. **Shipping a neural matcher is a hard requirement of the
project.** That is recorded in [ADR 0001](./adr/0001-neural-matcher-is-a-project-requirement.md)
and it is the single most important fact about this plan, because it changes what
the work is for.

The NN this ticket describes already exists and has already lost twice:

- `data/scripts/train_models.py::SmallNN` — MLP 84→64→32→16, ReLU, dropout 0.3,
  Adam + weight decay 1e-4, class-weighted soft-target cross-entropy from the
  panel vote distribution, early stopping, outer 5-fold CV.
- Current run (`data/training/model_selection.md`, features-v4, 232 rows, 16 careers):

  | model | top-1 | top-2 | balanced top-1 | ECE scaled |
  |---|---|---|---|---|
  | gbt_tuned | 0.772 | **0.892** | 0.715 | 0.047 |
  | logistic_tuned | 0.724 | 0.849 | 0.679 | 0.103 |
  | small_nn | 0.634 | 0.841 | 0.572 | 0.101 |
  | two_tower | 0.634 | 0.746 | 0.566 | 0.077 |
  | formula (reference) | — | 0.582 | — | — |

- The earlier 6-career run reached the same verdict (`docs/matching-rework-plan.md`).

Rev 2 framed the open question as *"can an NN win at n=232 / 84 features / 16
classes?"* — with a negative answer, properly evidenced, as a valid outcome. Under
a hard requirement that framing is dishonest: the NN ships either way, so a
contest whose result cannot change the outcome is theatre.

**The real question is: can we ship a neural matcher *honestly* — one that is
calibrated and stable enough to serve — and report truthfully where it stands
against the alternatives?** Everything below serves that.

## Constraint that bounds every claim below

Silver labels are ~94% circular with the `careers.json` bonus table. **No metric
here is evidence of real-world recommendation quality.** Everything measures
fidelity to a hand-authored weight table. See Step 4.

Vocabulary used precisely throughout — *Qualified*, *Selected*, *Servable*,
*Deployable*, *Ship Floor*, *Incumbent*, *Residual Matcher* — is defined in
[`CONTEXT.md`](../CONTEXT.md). These were used interchangeably in rev 2 and that
is what produced its circular deployability wording.

---

## Step 1 — Pin and install the training stack

`backend/venv` has none of numpy, pandas, scikit-learn, torch, lightgbm, pyarrow,
and nothing pins them anywhere. The Phase 2/3 scripts cannot run.

1. **A separate training virtualenv** — not `backend/venv`. That venv runs the
   service test suites, and mixing torch and lightgbm into it means every future
   `pip install` is an opportunity to move `numpy` and invalidate the digest this
   whole step rests on. Isolation is what protects the digest; pinning inside a
   shared, loosely-constrained environment does not.
2. **`data/requirements-training.in` → `data/requirements-training.txt` via
   `pip-compile --generate-hashes`**, so transitive dependencies and wheel hashes
   are pinned too, not just six top-level names. `dataset_digest()` hashes
   feature+label *content* via `pd.util.hash_pandas_object`, and numpy dtype
   promotion or a pyarrow parquet reader change can move that hash as easily as a
   pandas dtype change can.
3. **No pointer from root `requirements.txt`.** Root is entirely unpinned
   (`numpy>=1.20.0`, `pandas>=2.0.0` — the two packages the digest is most
   sensitive to). Putting the pinned training stack in the same resolution scope
   as those constraints is worse than leaving it out, and nobody deploying the
   services needs torch.
4. Direct versions are driven by the acceptance test below, not by "latest".
   Available for this interpreter (Python 3.14): numpy 2.5.1, pandas 3.0.5,
   scikit-learn 1.9.0, lightgbm 4.7.0, pyarrow 25.0.0, torch 2.13.0. First attempt
   pins the pandas 2.3.x line, since the recorded digest was produced before
   pandas 3's string-dtype and copy-on-write changes.
5. **Environment manifest** — full Python version, platform, and resolved
   versions of every digest-relevant package — emitted into *every* generated
   report, so any number can be traced to the environment that produced it.

**Acceptance test — the whole point of this step:** re-run `evaluate_matchers.py`
**completely unchanged** and confirm the emitted `dataset_digest` still equals
`2bdd5ec99d6a49a2a19c40163cf7a69d560453e3095bc6b4241c6065f18a4b27`, and that
logistic/lightgbm reproduce their recorded Gate-1 metrics (logistic ECE 0.0341 /
stability 0.6375; lightgbm 0.1282 / 0.5565). If the digest moves, the pin set is
wrong and **no result from that environment is comparable to the recorded
history** — stop and re-pin rather than re-baseline silently.

Note the division of labour: the digest test **detects** drift, the lockfile
**prevents** it, the manifest **attributes** a number to an environment. They are
not substitutes.

**Not re-run:** Phase 0 (panel labeling) and Phase 1 (dataset build). The parquets
exist and their digest matches both gate files, so no chromadb, no
sentence-transformers, no local LLM — and the standing rule that Phase-0
retraining needs explicit sign-off stays untouched.

---

## Step 2 — NN architecture and training rework

### 2.1 Shared, deterministic model module

`data/scripts/nn_model.py` exposing a scikit-learn-compatible `NNClassifier`
(`fit` / `predict_proba`), imported by both `evaluate_matchers.py` (Gate 1) and
`train_models.py` (Gate 2). One definition, no drift.

**Determinism is a hard requirement of this module**, for the reason in Step 3.2:
`random_state` is an explicit constructor argument; every `fit()` re-seeds torch
and numpy from it and disables nondeterministic backend kernels, so two fits on
identical data produce bit-identical predictions.

`train_models.py`'s `SmallNN` is replaced by this import; its stale `38->64->32->6`
docstring is corrected.

### 2.2 Variant sweep — 14 variants

> **Status: DONE (DEV-93, 2026-07-29).** Implemented as `sweep_variants.VARIANTS`,
> a registry of 14 frozen `Variant` records built by `sweep_variants.build_variant`.
> The sweep varies **arguments** to `nn_model.NNClassifier`; expressing Gaussian
> input noise and the SGD+cosine protocol required two additive constructor
> arguments (`input_noise`, `optimizer`/`lr_schedule`/`momentum`), whose defaults
> are inert — `test_variant_registry.py` requires the control Variant's predictions
> to be **bit-identical** to `NNClassifier(random_state=...)`, so `small_nn`'s
> recorded Gate-1 numbers still describe the same estimator. The 5-seed ensemble is
> `nn_model.SeedEnsemble`, its own Variant, never fused into the Residual Matcher.
> Symbol names, not line numbers.

Control: **V0** = current config (84→64→32→16, dropout 0.3, wd 1e-4, lr 1e-3, bs 32).

*Axis A — capacity* (4). Hypothesis: the current net is too large for 232 rows.
A1 `84→16→16` · A2 `84→32→16` · A3 `84→64→16` · A4 = V0 (control).

*Axis B — regularization* (5). dropout ∈ {0.1, 0.5} · weight decay ∈ {1e-3, 1e-2}
· Gaussian input noise σ=0.1.

*Axis C — protocol* (5). batch size 16 · full-batch · SGD+momentum with cosine
schedule · 5-seed probability-averaged ensemble · **C4, the Residual Matcher**.

That is **14 variants**, not the 12 rev 2 claimed. Axes are no longer applied
sequentially ("best of A, then B") — see 2.4; all 14 are fully specified up front
and compete in the same inner CV.

The 5-seed ensemble stays a **separate** variant rather than being fused into C4.
Fusing would confound two distinct effects — "does a non-linear residual help" and
"does seed-averaging help" — and a fused winner could not be attributed to either.
If C4 leads after round 1, ensembling is tested on top of it as a round-2
refinement, which also defers the 5-member serving artifact to the only branch
where it is real. (Integrated gradients is linear in the model function, so
attribution over a probability-averaged ensemble is just the average of the
members' attributions — ensembling costs artifact size and serve-time compute, not
explainability.)

### 2.3 C4 — the Residual Matcher

> **Status: DONE (DEV-92, 2026-07-29).** The model is `nn_model.ResidualMatcher`
> and its selection wiring is `train_models.select_residual_config` /
> `fit_residual` / `alpha_zero_verdict`; contract held by
> `data/scripts/tests/test_residual_matcher.py`. Symbol names, not line numbers, as
> in Step 4.2.
>
> **Wired into `train_models.main()` by DEV-93 (2026-07-29)** as a fifth Gate-2
> model, `residual_matcher`. DEV-92 deliberately held it out so its configuration
> would not be picked under a different protocol than the one every other Variant
> competes under; the round-1 sweep has now run, so that reason has expired. It is
> placed **after** `two_tower` in `main()` — `two_tower` seeds from process-global
> torch RNG rather than per fit, and running the new model last means "two_tower did
> not move" does not depend on `NNClassifier`'s state-restoration reasoning being
> right. It trains on **hard labels**, unlike `small_nn`: ADR 0003's paired
> comparison against `logistic_tuned` only holds while both optimise the same
> targets. `gate2_winner.json` now carries `residual_alpha_verdict`, the per-fold
> alpha record the ≥3-of-5 rule reads.

**`logits = frozen_logistic_logits + α · MLP(x)`**, with `α` a hyperparameter
selected by inner CV from `{0, 0.25, 0.5, 1.0}`. Full rationale in
[ADR 0003](./adr/0003-residual-matcher-freezes-its-linear-branch.md).

Rev 2 proposed training both branches jointly, warm-started at the logistic
solution with split weight-decay groups, and claimed this made the model
"structurally never worse than logistic". **That claim was false and is
retracted.** Initialisation constrains only the starting predictions; training
minimises soft-target cross-entropy while the reported metric is top-2, and early
stopping selects on validation loss, so the network can and does finish below its
own initialisation. An unregularised linear branch also drifts off sklearn's L2
solution from the first step.

What the frozen form gives instead:

- The logistic branch is **fitted on whatever partition the MLP trains on** and
  then held fixed. It has no parameters to decay, so rev 2's split
  parameter-group machinery disappears entirely.
- Its regularisation `C` is **inherited from that outer fold's `logistic_tuned`
  selection**. That value was chosen using only outer-training data, so reusing it
  inside inner splits of the same partition does not touch the outer test set —
  and it makes C4's base exactly the Incumbent's configuration, turning "does the
  residual add anything?" into an exactly paired comparison. (Selecting `C` at a
  third nesting level is the purist option and does not earn its complexity.)
- With `α = 0` the model is *exactly* logistic regression, so inner CV can always
  retreat there. This is a **selection safeguard, not a guarantee on unseen data.**
- Attribution splits cleanly: the frozen branch keeps exact linear attribution and
  IG covers only `α · MLP`. If `α = 0` is selected there is no IG at all.

**Pre-registered:** `α = 0` selected in ≥3 of 5 outer folds is reported as
**"no non-linear signal found"** and disqualifies the Residual Matcher from being
the shipped neural model — shipping it would be shipping logistic regression in a
costume while the project requires a neural network. If that happens, the shipped
model is the best genuinely non-linear variant and **the cost of that substitution
is reported explicitly**.

Why fund C4 at all: `gbt_tuned` beats `logistic_tuned` on top-2 by 0.043 — roughly
10 profiles. That is the only evidence in the whole run suggesting exploitable
non-linear structure exists in these features. It is suggestive, not established,
since nobody has run seed variance on it. But if it is real, a residual learner is
the right shape to capture it.

### 2.4 Search protocol — nested, unpruned, and paired

> **Status: DONE (DEV-93, 2026-07-29).** Variant selection is
> `sweep_variants.select_variant`, which delegates to the existing
> `train_models.select_by_inner_cv` rather than adding a second grid-argmax — so
> "no separate selection stage exists" is a property of the code, not only of the
> plan. `outer_folds`, `cross_fitted_oof`, `select_by_inner_cv` and
> `select_residual_config` gained a `random_state` for the 5-seed protocol; **every
> default is the single-seed path**, so the DEV-91 Gate-2 re-baseline stays
> reproducible. `test_variant_selection.py` holds the no-leak contract the way
> `test_cross_fitted_temperature.py` holds the calibration one: it poisons every row
> outside the training partition and requires the selection not to move. Two errors
> in this section were corrected by that ticket — see the call-outs below.

**Rev 2's pruning pass is deleted.** It scored variants on the outer-fold-1
training partition — which, under 5-fold CV, is *precisely the union of the test
sets of folds 2–5*. Variant selection would have seen 100% of the evaluation data
for four of five folds, leaving only fold 1's test set clean and making a pooled
OOF number 80% contaminated.

1. **All 14 variants compete inside every outer fold's inner 3-fold CV.** No
   separate selection stage exists, so there is no stage that can leak.
2. **This is comparable search to what the Incumbent already gets — not
   dramatically less.** `gbt_tuned` selects from `GBT_GRID`, a `product` of four
   2-element lists, nested in every outer fold; `logistic_tuned` from
   `LOGISTIC_C_GRID`, 4 points.

   > **Corrected by DEV-93.** Rev 3 claimed a "32-point grid" at
   > `train_models.py:53`. Both halves were wrong: `GBT_GRID` is
   > 2×2×2×2 = **16** points, and it is not at line 53. The
   > "less search than the Incumbent already gets" argument was overstated by 2×.
   > **The honest version:** 14 NN Variants against gbt's 16 is *approximately the
   > same* search budget, not a fraction of it. That still defeats "the NN was
   > tuned harder than the Incumbent" — it is not tuned harder — but it no longer
   > supports a claim of restraint, and it is a weaker rebuttal to "the NN wasn't
   > tried hard enough" than rev 3 implied. Round 2's ≤6 refinements would put the
   > NN's total ahead of gbt's; that is a real cost of the second round and should
   > be stated when it is spent. Cite symbols, not line numbers.
3. **Seeds sit outside selection.** Inner CV runs single-seed; each of the 5
   experiment seeds gets its own complete nested run. The experiment seed varies
   **both the fold partition and initialisation** — 5 repeats of the entire nested
   CV — so `mean ± sd` is meaningful for gbt and logistic too, not just the NN.
   Fold assignment at n=232 with `game-dev` at 5 labels is a genuine variance
   source; freezing it hides that rather than controlling it. Within each seed all
   three models share folds, so the pairing is fully preserved.
4. **Paired comparison, not mean-vs-mean.** Primary analysis: a **paired bootstrap
   whose sampling unit is the profile** (10k resamples over the 232 profile IDs).
   Per profile, the top-2 hit indicator is **averaged across the 5 seeds first**,
   then differenced against the comparison model. Seeds are carried inside the
   unit, never resampled as if they were independent observations — treating
   1,160 profile-seed rows as independent would understate the standard error by
   about √5 ≈ 2.2×.
5. **What that CI covers**, stated in the report: profile sampling variability
   *conditional on the seeds drawn*. It does not fold in seed variability, and a
   two-way bootstrap over 5 seeds would be hopelessly underpowered on the seed
   dimension. Per-seed paired results are reported as a table instead.

Points 4–5 matter: `small_nn` top-2 **0.845** vs `logistic_tuned` **0.849** is
**0.004** — *one* profile out of 232, and nobody has ever run seed variance on
these numbers. **The existing "the NN lost" conclusion may be inside noise.** That
cuts both ways: it is equally unsafe to conclude the NN is competitive.

> **Corrected by DEV-93.** Rev 3 argued from the pre-DEV-90/DEV-91 pair
> (0.841 vs 0.849 = 0.008, "about 2 profiles") and carried DEV-91's correction as
> a trailing annotation, so the *argument* still ran on the stale number while the
> footnote disagreed with it. The corrected figures are now in the paragraph
> itself. The argument gets **stronger**: a one-profile gap is even more clearly
> inside the noise a 5-seed protocol is built to measure. `small_nn`'s move from
> 0.841 to 0.845 is a DEV-90 re-seeding effect, not a calibration one — see
> `data/training/model_selection.md`.
>
> Knock-on for 2.5's materiality marker: 0.02 is **5×** the disputed 0.004, not
> the 2.5× rev 3 computed against 0.008.

### 2.5 Effect size — a reporting standard, not a gate

> **Status: DONE (DEV-93, 2026-07-29).** `sweep_variants.paired_bootstrap`. The
> sampling unit is the **profile**: each profile's top-2 hit indicator is averaged
> across the 5 seeds *first*, then differenced, then the 232 profile ids are
> resampled. `test_paired_bootstrap.py` pins that with a property a row-resampling
> implementation cannot satisfy — five identical replicate seeds carry no
> information and must not move the interval at all — and it was verified to fail
> 5/5 against such an implementation before being kept.

Under a hard requirement this no longer authorises anything; it sizes the gap. The
machinery is kept because "how far behind is the shipped model?" is the most
useful number in the deliverable.

Reported for the shipped NN against `logistic_tuned` and `gbt_tuned`:

- **δ on pooled OOF top-2**, with the 95% paired-bootstrap CI from 2.4.
- Whether δ ≥ 0.02 — the threshold rev 2 pre-registered for displacement, retained
  as a **materiality marker**. 0.02 ≈ 1 profile per outer fold, ≈ 4.6 profiles
  overall, and **5×** the disputed 0.004 gap (corrected in 2.4; rev 3 said 2.5×
  against the stale 0.008).
- **Seed stability:** whether the sign of δ holds in ≥3 of 5 individual seeds. A
  result that flips across seeds is reported as unstable, and instability is
  itself a finding about the architecture.

### 2.6 Learning curve

> **Status: DONE (DEV-96, 2026-07-31).** `data/scripts/learning_curve.py`, report
> `data/training/learning_curve.md`. Five things this step did not settle, decided
> here and stated in the report rather than applied quietly:
>
> 1. **The frozen configuration is a five-member ensemble.** "Architecture and
>    hyperparameters frozen at the selected configuration" resolves to
>    `SeedEnsemble(n_members=5, dropout=0.5, weight_decay=1e-2)`, so every neural fit
>    on the curve is five fits and the curve measures an *ensemble*. Read from
>    `selected_specification` in `round2_results.json` and checked field-by-field
>    against the registry entry, so the curve cannot measure a later edit of it.
> 2. **The validation rule is an additive absolute-size argument**,
>    `NNClassifier(val_size=)`, not a per-point `val_fraction`. That float is handed
>    to `train_test_split`, which takes `⌈fraction·n⌉`, and `n_val/n_train` is not
>    guaranteed to round back to the integer it came from. `None` is inert, so
>    `test_variant_registry.py`'s bit-identity contract still holds.
> 3. **The comparators are NESTED at every point, not frozen.** Rejected on
>    correctness, not budget: freezing means either an arbitrary configuration, which
>    is no longer the `gbt_tuned` this deliverable reports a gap against, or one
>    selected on all 232 rows — which would have seen data outside every subsample
>    below 232, i.e. Leakage at four of the five points.
> 4. **Comparator selection runs under 2 inner folds, at every point.** At n=48 an
>    outer training partition holds two rows of the rarest classes; a 3-fold inner
>    split loses a class, sklearn warns rather than raises, and the selection metric
>    would then read top-2 indices meaning different careers. One rule everywhere, not
>    a per-point accommodation — and one more reason these numbers are not comparable
>    to a gate number.
> 5. **The subsample is a function of the curve point alone and does not vary with
>    the experiment seed.** "The 80 profiles common to both points" is one set only if
>    every seed cuts the same subsample. The cost — every number is conditional on one
>    subsample draw — is disclosed in the report.
>
> Nesting is by construction rather than by apportionment: one global ordering of the
> surplus rows, every point a prefix of it, so proportional rounding cannot hand a
> class fewer rows at a larger `n`. `test_learning_curve.py` pins nesting, the class
> floor, the balance table, the validation rule, `val_size`'s inertness and the
> Δgap contrast's algebra.

Its job has changed and grown. Rev 2 wanted it as insurance against "you didn't
try hard enough" if the NN lost. It is now the evidence for **how far behind the
shipped model is and whether more data would close the gap** — the most actionable
thing in the deliverable, and a direct input to whether collecting more labels is
worth funding.

**Protocol constraint that shapes the design.** `train_test_split(...,
test_size=0.15, stratify=ytr)` (`train_models.py:232`) requires
`⌈0.15·n_train⌉ ≥ 16`. Under 3-fold CV that fails at *three* of rev 2's five curve
points, not one:

| n | outer-train rows | requested val rows | feasible under rev 2? |
|---|---|---|---|
| 48 | 32 | 5 | **no** |
| 80 | 53 | 8 | **no** |
| 116 | 77 | 12 | **no** |
| 174 | 116 | 18 | yes |
| 232 | 155 | 24 | yes |

This is purely a curve problem — the live 5-fold protocol at n=232 gives 186
training rows and 28 validation rows.

Design:

- **One validation rule at every point:** `n_val = max(n_classes, ⌈0.15·n_train⌉)`.
  Rev 2's alternative — a frozen epoch budget — is rejected: the optimal epoch
  count genuinely falls as n falls, so a budget tuned at n=232 would systematically
  over-train the small-n points and **manufacture the very narrowing the curve is
  supposed to test for**.
- **Architecture and hyperparameters frozen** at the selected configuration (the
  curve measures data size, not selection); **epoch count still determined per fit
  by early stopping** under the rule above. Freezing the *configuration* is not
  the same as freezing the *epoch budget*.
- Dedicated **3-fold protocol**, all three models, same subsamples, **5 seeds each**.
- Curve points **n ∈ {48, 80, 116, 174, 232}** via class-floored stratified
  subsampling (each class keeps `min(count, floor)`, remaining budget drawn
  proportionally from the surplus).
- **n=48 is reported but annotated "protocol floor — 1 training example per class,
  not a data-size measurement".** It is shown so nobody can claim the hardest point
  was quietly dropped; it is excluded from the test because a model trained on 16
  rows is bad for reasons that have nothing to do with the trend.
- Stated explicitly: these numbers are **not comparable to the 5-fold gate numbers**.

**Pre-registered reading of the curve.** Rev 2's "non-overlapping CIs" rule is
replaced — it is a low-power proxy and not even the quantity of interest. The
quantity is **Δgap = gap(n=232) − gap(n=80)**, with a 95% CI from the same
paired-bootstrap machinery, computed **over the 80 profiles common to both points**
(subsamples are nested, so the n=80 point only has predictions for 80 profiles).

- **"Narrowing"** = the CI on Δgap excludes zero in the narrowing direction.
- Anything else is reported as **flat / inconclusive**. No trend is claimed from a
  point-estimate slope.

**Class-balance confound — stated, because it is severe here.** Class-floored
subsampling makes the small-n points *more balanced* than the large-n points, so
balance and n move together and any gap trend is partly a balance trend:

| n | most-represented class | least | max:min skew |
|---|---|---|---|
| 48 | 3 (6.3%) | 3 | **1.0 — perfectly uniform** |
| 80 | frontend ≈11 (13.8%) | 3 | ≈3.7 |
| 232 | frontend 47 (20.3%) | game-dev 5 | **9.4** |

The two effects push in *opposite* directions — small n is harder for data-size
reasons but easier for balance reasons — so an observed narrowing could be a
balance effect. The report prints the skew at every curve point beside the gap.

**Balance-controlled control curve:** n ∈ {64, 80} at *uniform* k ∈ {4, 5} per
class. `game-dev`'s 5 labels cap uniform balance at n=80, and k=3 is dropped for
the same protocol-floor reason as n=48 — which leaves two points. It is therefore
explicitly a **two-point sanity check, not a trend**, and is barred from carrying
any interpretive weight beyond that.

### 2.7 Ship floor — replacing the kill criteria

> **Status: round 2 evaluated, budget spent (DEV-95, 2026-07-30).**
> `data/scripts/sweep_round2.py`, report `data/training/nn_rework_round2.md`. **There
> is no round 3.** Three things this step did not anticipate, recorded here rather
> than left in the ticket:
>
> 1. **"≤6 refinements around the round-1 best" stopped parsing, and was
>    reinterpreted openly.** The round-1 best is the Residual Matcher at `α = 0`,
>    which is bit-identical to logistic regression; refining around it means either
>    tuning logistic regression or widening the `α` grid, and ADR 0003 calls the
>    latter a protocol change rather than a tuning tweak. Round 2 reads "the round-1
>    best" as **the best of the models still eligible to be the deliverable** — the
>    best genuinely non-linear Variant — because ADR 0003's disqualification clause
>    makes that the model which actually ships.
> 2. **Round 1 could not name that Variant, because the evidence had been thrown
>    away.** `select_by_inner_cv` returned the argmax and discarded the other
>    thirteen scores, so the ranking among the never-selected Variants was computed
>    25 times and lost 25 times. DEV-95 added an additive out-channel
>    (`select_by_inner_cv(..., scores_out=)`) and re-ran the contest; all 25 Round-1
>    selections reproduced.
> 3. **The Residual Matcher does not compete in round 2.** A contest selects the
>    model that ships, and ADR 0003 has ruled that it may not be that model. Its
>    round-1 numbers stand and its per-contest counterfactual score is reported as
>    the substitution cost the ADR requires.
>
> **Status: round 1 evaluated (DEV-93, 2026-07-29).** `sweep_variants.evaluate_ship_floor`
> scores **one exact configuration** — the modal Variant across all 25 (seed, outer
> fold) selections — because Qualified is a property of a configuration and is never
> inherited by a reconfigured model (`CONTEXT.md`). The ordering constraint is
> enforced rather than remembered: `assert_deterministic` raises `SystemExit`, so
> there is no code path that produces a stability number without it having passed
> first. Verdict for round 1: `data/training/nn_rework.md`.

Rev 2's kill criteria assumed abandoning the NN was possible. It is not, so
"budget kill, no round 3" is not a criterion but a dead end with nothing behind it.
What replaces it is a floor, split into a hard half and a mitigable half — full
reasoning in [ADR 0002](./adr/0002-gate-1-is-a-ship-floor.md).

- **Top-2 stability ≥ 0.60 — hard, unmitigable.** An unstable model gives
  different recommendations to the same user depending on which resample trained
  it. The ranking *is* the product; there is nothing to degrade into.
- **ECE ≤ 0.10 — mitigable.** It matters because `Results.jsx` renders
  `matchPercent`. A model failing it may still ship as the *ranking* source with
  displayed percentages falling back to the formula's.
- **Gated on the determinism check in Step 3.2 passing first** — the stability
  floor may not fire on a measurement artifact.
- **Search budget:** round 1 (14 variants) plus round 2 (≤6 refinements around the
  round-1 best). No round 3.

**If no variant clears the stability floor after both rounds, this escalates as a
project-level finding** — "this dataset cannot support a stable 16-class neural
matcher at n=232" — rather than shipping something arbitrary. That is a real,
defensible, reportable result and it is information whoever set the requirement
needs.

Known achievable on this data: `logistic_tuned` clears both (ECE 0.0341,
stability 0.6375).

---

## Step 3 — Gate 1 integration

### 3.1 The NN becomes a real gate candidate

`evaluate_matchers.py:283` hardcodes `learned = ("logistic", "lightgbm")`. The NN
has never been gate-scored; its rejection has always been an assertion in a
Phase-3 report, not a gate verdict.

- `learned = ("logistic", "lightgbm", "small_nn")`, scored through the existing
  `cv_oof_and_stability()` — same folds, same thresholds, no special-casing.
- `gate1_verdict.json` gains a `small_nn` entry under `metrics`, and under
  `qualifiers` if it clears. Schema shape unchanged, so nothing downstream breaks.
- **Hard vs soft targets:** the Gate-1 wrapper is fed `(X, y)` hard labels like
  every other gate candidate. The soft-target variant stays a Gate-2 challenger.
  The asymmetry is documented and handled by the pattern already in the repo —
  export revalidates the **exact shipped configuration** against the Gate-1
  thresholds, because qualification never transfers across configurations.
- **Rev 2's `SERVABLE` set is dropped.** It made servability an input to
  *selection*, which is backwards: servability is an input to *deployment*, and
  selection should not know about it. See Step 6.

### 3.2 Stability must be measured comparably — verified, not assumed

`cv_oof_and_stability()` measures top-2 set agreement between sub-models trained on
inner resamples. For logistic that variation comes *only* from the training subset,
because the estimator is near-deterministic. A NN with dropout and random init
would additionally vary from its own randomness — so it would be scored on a
noisier estimator than its competitors, and the stability floor could fire on a
measurement artifact rather than on real instability.

Mitigation, a precondition rather than a nicety:

- `NNClassifier` is constructed with a fixed `random_state` (Step 2.1), so refits
  on identical data are bit-identical and the only surviving source of variation is
  the training subset — the same thing being measured for logistic.
- **A determinism assertion runs for all three candidates before any stability
  number is trusted:** fit twice on identical data, assert identical
  `predict_proba` output. The Step 2.7 stability floor is blocked until this passes.
- Separately reported (not gated on): stability across *reseeded* NN runs, which is
  a genuinely interesting property of the NN and is stated as its own number rather
  than smuggled into a comparison with logistic.

---

## Step 4 — Label circularity and calibration: two separate defects

Rev 2 conflated these. They are independent, and only one of them needs better
labels.

### 4.1 Circularity — documented, not engineered around

No NN work addresses this and none is attempted.

1. A **Validity** section stating plainly that every gate metric is agreement with
   an LLM panel whose stage-2 vote follows the `careers.json` bonus-derived answer
   key ~94% of the time it speaks. Fleiss κ ≈ 0.88–0.92 is panel self-consistency,
   not corroboration. The paired-bootstrap CIs quantify sampling variability
   **within a circular dataset** and inherit its bias entirely.
2. What a **non-circular validation would require**, scoped as future work and not
   implemented: a Gold Slice of ~80–120 profiles labeled by ≥3 human practitioners
   who did not author the bonus table, stratified across all 16 careers.
3. The existing `build_caveats()` mechanism embeds the circularity caveat **inside**
   the artifact so it reaches `RecommendationsResponse.model_caveats`, the persisted
   history jsonb, and `Results.jsx`. The NN artifact format must carry `caveats`
   identically — hard requirement, covered by the Step 5.2 export tests.

### 4.2 Calibration — a fitting bug, fixable now

> **Status: DONE (DEV-91, 2026-07-28).** Implemented as `cross_fitted_oof()` in
> `train_models.py`, driving all four models; contract held by
> `data/scripts/tests/test_cross_fitted_temperature.py`. Symbol names, not line
> numbers, below — every line reference in this plan had drifted by 11–20 lines by
> the time this step ran, and this step restructured the file again.

`temperature_scale()` in `train_models.py` fitted a single temperature on the
pooled OOF predictions and the metrics loop scored ECE on those same predictions.
Rev 2 filed this under "prototype-grade, a gold slice is the fix". **A gold slice
would not fix it** — you would reproduce the same bug on better labels. Full record
in [ADR 0004](./adr/0004-temperature-is-cross-fitted.md).

The bias is not uniform across models: a worse-calibrated model gains more from
fitting T on its own evaluation data, and that quantity is the Gate-2 tiebreaker,
so it can flip a winner.

Fix — cross-fitted temperature, per outer fold:

```
for (tr, te) in outer:
    config    = select_by_inner_cv(tr)
    inner_oof = OOF probabilities over tr from 3 inner refits of config
    T_fold    = fit_temperature(inner_oof, y[tr])      # never sees te
    oof[te]   = apply_T(fit(config, tr).predict_proba(X[te]), T_fold)
```

- Both raw and cross-fitted ECE are reported; the tiebreak uses the cross-fitted one.
  *Added by DEV-91, beyond what this step originally asked for:* a third ECE column
  (the legacy pooled-T number) and two NLL columns. The legacy column earns its
  place by separating `small_nn`'s two causes of movement, which is otherwise not
  recoverable; the NLL columns exist because the direction of the change turned out
  to be the thing readers assume they already know. Both are reported, neither
  gates.
- **The five per-fold `T` values and their spread are reported.** Wide spread means
  any single pooled temperature for that evaluated configuration is not a
  well-estimated quantity.
- Gate 1 is unaffected — it gates on raw ECE and never applied a temperature.
  Verified, not assumed: `evaluate_matchers.py` was re-run and reproduced the
  digest and every Gate-1 metric to the last digit.
- Phase 3 records a pooled temperature for each evaluated configuration.
  `export_model.py` requires that calibration record rather than silently
  defaulting, but cannot transfer the value when its selected fixed C differs from
  Phase 3's heterogeneous per-fold Cs. It refits on pooled OOF predictions from
  the exact fixed-C configuration and writes that result. Since DEV-88 made the
  serving path divide logits by this field, a non-1.0 value changes served
  `matchPercent` the moment such an artifact is loaded.

**Sequencing, non-negotiable:** reproduce the recorded numbers on unchanged code
first (Step 1's acceptance test), *then* apply this fix, *then* re-baseline all
four models together. **Every recorded Gate-2 `ece_scaled` and `temperature`
becomes non-comparable to history**, including the `gbt_tuned` ECE 0.047 that won
it Gate 2. That is a deliberate, documented break, not silent drift.

---

## Step 5 — Explainability

### 5.1 The q11–q18 discarded-attribution defect — own ticket, but a hard prerequisite

`reason_builder.py:18` defines `QUESTION_PHRASES` for q1–q10 only, **and that dict
is also the iteration set** (`:72`). The bank is 18 questions, so q11–q18
attributions are silently discarded today.

The arithmetic matters. The feature vector is 2·18 + 3·16 = 84. Of the 36 question
features, **16 belong to q11–q18 — 44% of the question-feature attribution surface,
discarded.** And q11–q18 are the pure discriminators: zero questionnaire weight,
signal carried entirely by per-option bonuses. They are precisely the features a
learned model has most reason to lean on.

This degrades production output **right now**, on the currently-served path, so it
ships as **its own ticket and its own branch off `main`** and merges on its own
schedule. It is **removed from DEV-23's sequential execution order** — the variant
sweep must not wait on a Jira approval.

**But it is a hard prerequisite of the NN serving merge.** Shipping the NN before
it means computing integrated-gradients attributions correctly and then throwing
them away for nearly half the question surface, making Step 5.2's explainability
work partly decorative. Off the critical path, ahead of the serving milestone.

Test design — a coverage assertion alone is too weak, since it catches a missing
q19 but not a phrase that exists and is wrong:

- **Coverage:** `QUESTION_PHRASES` covers every id in `questions.json`.
- **Attribution mass:** over representative feature vectors, the share of
  explainable attribution mass that is actually renderable must be ≥ 0.99 —
  measured against the *explainable universe* (own-career fit/sem/skill + all
  question features), since cross-career coefficients are deliberately withheld as
  honest-but-unreadable. This is what catches a silently-dropped question block.
- **Wording drift:** a snapshot pairing each question's current text with its
  phrase. Automation cannot verify that a phrase is semantically right, but it can
  force a human re-read whenever the question text changes — a demonstrated failure
  mode here, since DEV-73 reworded q7 after these phrases were authored.

### 5.2 Serving path — core scope, not conditional

Rev 2 made this conditional on the NN winning and called it "the only large
conditional block". Under the requirement it is unconditional and it is the
**largest block of work in the ticket**.

**Dispatch seam — landed first, unconditionally.** A `Matcher` protocol
(`predict_proba`, `contributions`, `feature_names`, `version`, `caveats`) plus a
module-level `load_matcher(path)` that validates, reads `model_type`, and returns
the right implementation. `MatcherModel` is touched in exactly four non-test places
— `main.py:46`, `internal.py:17`, `matching_service.py:299/:314` — so this is small:
two type hints widen, `main.py` calls the factory, the rest is untouched. A free
function, not a classmethod returning a sibling class.

Landing it before any NN code means the NN branch adds one class implementing an
interface that already exists and already has passing tests, rather than performing
a structural refactor in the same change as new inference code.

**The `temperature` field starts being applied**, in the same change. The artifact
has carried it since `export_model.py:159` and `MatcherModel.__init__` has never
read it. At the DEV-88 landing it was `1.0`, so applying it was provably inert. A
later exact-configuration export fit can produce a non-1.0 value (the fixed-C
artifact now reproduces 1.05), at which point this path deliberately changes
served probabilities.

**`services/matching/app/services/matcher_nn.py`** — forward pass in **numpy**, no
torch. Rev 2 specified stdlib-only, mirroring `matcher_model.py`'s posture; but
`numpy>=1.24.0` is already a declared dependency of the matching service and
already loaded in-process. The real requirement is *no torch at serve time* — torch
is heavyweight and slow to import; numpy is neither, and it is already there. Under
stdlib-only, IG at m=32 is roughly 760k pure-Python float operations per career
explained, which lands around 100–250 ms of added latency per request and makes the
step count a budget decision rather than a correctness one.

**Integrated gradients**, with an honest exactness claim. For a ReLU net the
*theorem* is exact — `f` is piecewise-linear along the straight path — but a fixed
32-step **Riemann sum** is not, because the gradient along that path is a step
function that jumps at activation breakpoints. Rev 2's "exactness guarantee
analogous to the linear case" overclaimed in the same way its C4 description did.

- Baseline = scaler mean (the z=0 vector); attributions centered across classes
  exactly as `contributions()` does.
- **Adaptive `m`:** start at 32, double until the relative completeness residual is
  < 1e-3, cap at 512, record the achieved residual. A measured guarantee per
  request rather than a hoped-for one.
- **Completeness is asserted on the centered logit actually explained**, not the
  raw one — centering is linear so completeness survives it, but asserting the
  uncentered identity would pass while the shipped quantity was wrong.
- **If the residual cannot be brought under tolerance even at m=512, that career
  emits no model-derived reasons** and falls through to the non-model wording.
  Better silence than attributions that do not sum to what they claim to explain.
- Analytic breakpoint tracking is rejected: exact, but it means enumerating
  activation-pattern changes through two hidden layers — far beyond the ~30-line
  budget and a correctness risk of its own.
- Returns the same `dict[feature_name, float]` shape, so `reason_builder` is
  untouched and the user-facing UX is identical. SHAP rejected: heavier
  dependency, weaker guarantee here.

**`export_nn_model.py`**, mirroring `export_model.py`, including Gate-1
revalidation of the exact exported configuration and `caveats` carried identically
(4.1 item 3). **Parity tests** comparing torch and numpy logits/probabilities over
the complete dataset plus randomized vectors — and confirm whether the linear path
already has the sklearn-vs-stdlib analogue, adding it if not.

---

## Step 6 — Decision, and the line I will not cross

**Two phases, in order.** Rev 2's wording was circular — the NN had to be servable
to be selected, but its serving path was built only after selection.

1. **Statistical (knows nothing about serving).** Gate 1 qualification, Gate 2
   ranking, effect-size reporting versus `logistic_tuned` and `gbt_tuned`. Emits a
   *Selected* candidate and makes no deployability claim.
2. **Engineering.** Build the adapter, export, revalidate the exact exported
   configuration against the Gate-1 thresholds, confirm caveats survive. Only then
   does anything become *Deployable*.

| outcome | Gate-2 report | production default |
|---|---|---|
| No NN clears the stability floor | reported | **escalate** — do not ship |
| NN clears floor, materially behind logistic | qualified, gap reported | **NN** (requirement), gap documented prominently |
| Residual Matcher best but α=0 in ≥3/5 folds | "no non-linear signal found" | best genuinely non-linear variant; substitution cost reported |
| `gbt_tuned` wins Gate 2 | gbt winner, unservable | **NN** — gbt cannot serve, by scope |
| NN wins Gate 2 | NN winner | **NN** |

Note the fourth row: displacement is judged against the **Incumbent**
(`logistic_tuned`), not against the Gate-2 winner, because `gbt_tuned` cannot serve
by an explicit scope decision and therefore says nothing about whether the NN is
better than the model it actually replaces. This generalises the rule already
encoded at `train_models.py:399-403` so its fall-through target is not hardcoded.
The implication, stated rather than discovered: a measurably better model may sit
on the shelf unservable. That is already true today for logistic.

**The honest framing, which must appear in `docs/dev-23-nn-decision.md`:** these
metrics can rank learned models against *each other*, because they all face the
same circular labels. They **cannot** justify replacing the *formula* — the formula
is a hand-authored weight table and the labels largely encode that same table, so
"learned model beats formula on panel agreement" is close to tautological.
Switching away from the formula trades a transparent hand-authored rule for a model
that has learned that same rule, with **no independent evidence that either serves
users better**. The neural matcher ships because the project requires it. Its
standing against `logistic_tuned` and `gbt_tuned` is reported in full, with paired
CIs, and the requirement is named as the reason it serves. Getting this sentence
wrong is the one thing that would make the deliverable indefensible.

**I will not flip `MATCHER_MODEL_PATH` in `.env.example`, `backend/.env`, or
`docker-compose.yml`.** The artifact and adapter land; the switch is an explicit
separate step, surfaced for your approval.

**Also corrected:** `CLAUDE.md` claims the checked-in artifact is stale
features-v1/v3 and refused on load. Out of date — `matcher_logistic_v2.json` is
features-v4, matches `FEATURE_VERSION`, and loads fine. That stale line is likely
why the "nothing is deployable" impression persisted.

---

## File touch points

| file | change |
|---|---|
| `data/requirements-training.in` / `.txt` | new — hashed lockfile, separate training venv |
| `data/scripts/nn_model.py` | new — shared deterministic `NNClassifier`, Residual Matcher |
| `data/scripts/evaluate_matchers.py` | NN in `learned`; determinism assertion; env manifest |
| `data/scripts/train_models.py` | shared NN import; 14-variant nested sweep; cross-fitted temperature; paired bootstrap; stale docstring |
| `data/scripts/learning_curve.py` | new — 3-fold curve, class-floored subsampling, Δgap CI |
| `data/training/gate1_verdict.json`, `gate2_winner.json` | regenerated |
| `data/training/baseline_evaluation.md`, `model_selection.md` | regenerated (Gate-2 re-baseline) |
| `data/training/nn_rework.md` | new — sweep, seed variance, paired CIs, floor trace |
| `data/scripts/sweep_round2.py` | new — round-2 refinements, the recovered per-Variant scoreboard, final floor |
| `data/training/nn_rework_round2.md`, `round2_scoreboard.json` | new — round 2 and the substitution evidence |
| `data/training/learning_curve.md` | new |
| `services/matching/app/services/matcher.py` | new — `Matcher` protocol + `load_matcher()` |
| `services/matching/app/services/matcher_model.py` | implements protocol; applies `temperature` |
| `services/matching/app/services/matcher_nn.py` | new — numpy forward pass + adaptive IG |
| `services/matching/app/main.py` | calls `load_matcher()` |
| `data/scripts/export_nn_model.py` | new — mirrors `export_model.py`, revalidates, carries caveats |
| `services/matching/tests/` | protocol, parity, IG completeness, temperature application |
| `docs/dev-23-nn-decision.md` | new — decision, numbers, validity section |
| `CONTEXT.md`, `docs/adr/0001`–`0004` | created (this session) |
| `CLAUDE.md` | correct stale "artifact is refused" claim |
| **separate ticket/branch** | `reason_builder.py` q1–q18 + three tests — prerequisite of the serving merge |

## Execution order

Rev 2 front-loaded work that was valuable under every outcome, to avoid waste if
the NN died at round 1. That logic dissolves: the NN ships, so nothing is wasted.
The order is now driven by dependencies alone.

1. **Step 1** — separate venv, hashed lock, manifest, digest acceptance test.
   **Stop if the digest moves.**
2. **`CLAUDE.md`** correction.
3. **Dispatch seam** (5.2): `Matcher` protocol, `load_matcher()`, temperature
   applied. Zero behaviour change, fully testable today.
4. **Step 2.1 + Step 3** Gate-1 plumbing, including the **determinism assertion**.
5. **4.2 cross-fitted temperature** + one-time Gate-2 re-baseline of all four
   models. Only after step 1 has proven the environment. — **DONE (DEV-91,
   2026-07-28).**
6. **Round 1** — 14 variants, nested, 5 seeds. Evaluate the ship floor.
   — **DONE (DEV-93, 2026-07-29):** `data/scripts/sweep_variants.py`,
   report `data/training/nn_rework.md`. The same ticket wired the Residual Matcher
   into the Gate-2 run as a fifth model with its pre-registered alpha record.
7. **Round 2** if warranted (≤6 refinements). Evaluate the ship floor. **No round 3.**
   — **DONE (DEV-95, 2026-07-30):** `data/scripts/sweep_round2.py`, report
   `data/training/nn_rework_round2.md`. The search budget is now spent.
8. **Learning curve** (2.6) + control curve.
   — **DONE (DEV-96, 2026-07-31):** `data/scripts/learning_curve.py`, report
   `data/training/learning_curve.md`. The comparator legs are computed **fresh**:
   Rounds 1 and 2 could reuse each other's because within a seed the fold partition
   is a function of the seed alone *under the same protocol*, and the curve is a
   different protocol.
9. **`matcher_nn.py`, `export_nn_model.py`**, parity and IG-completeness tests.
   *Merges after the q11–q18 branch.*
10. **Steps 4 + 6 writeups** with real numbers; `docs/dev-23-nn-decision.md`.
11. Report and **wait** on the `MATCHER_MODEL_PATH` question.

*In parallel, off the critical path:* the q11–q18 ticket and branch off `main`
(5.1), which must merge before step 9.

## Estimates

**Compute is not the cost.** Implementation is.

- Step 1: ~10 min plus torch CPU download; re-pinning iterations if the digest moves.
- Round 1: per experiment seed, 5 outer folds × (14 variants × 3 inner fits + refit
  + 3 cross-fit temperature fits), with the ensemble variant costing 5× per fit —
  **≈ 1,450–1,850 NN fits total across 5 seeds**. Single-digit seconds per fit at
  n=232, so under an hour. Paired bootstrap at 10k resamples is seconds.
- Learning curve: 5 points × 3 models × 3 folds × 5 seeds ≈ 225 fits, plus the
  control curve (2 points × 3 × 3 × 5 = 90) and a paired bootstrap per point.
  Minutes.
- **Step 5.2 is the dominant block** — dispatch seam, numpy inference, adaptive IG
  with completeness assertions, export with revalidation, and parity tests across
  two runtimes. It is no longer conditional and it is the bulk of the ticket. Rev
  2's estimates covered the training runs and essentially none of this.
