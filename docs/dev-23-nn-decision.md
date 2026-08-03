# DEV-23 — The neural matcher: what shipped, how it stands, and what the numbers mean

DEV-98. Plan [`dev-23-nn-rework-plan.md`](./dev-23-nn-rework-plan.md) Steps 4 and 6.
Vocabulary is [`CONTEXT.md`](../CONTEXT.md)'s. Decisions are ADRs
[0001](./adr/0001-neural-matcher-is-a-project-requirement.md)–[0004](./adr/0004-temperature-is-cross-fitted.md).

Every number below is read back from a results file in `data/training/` or from the
artifact itself; none is transcribed from an earlier document. Sources are named at
each table.

---

## The framing, which governs how every number here may be read

**These metrics can rank learned models against *each other*, because they all face
the same circular labels. They cannot justify replacing the *formula*.** The formula
is a hand-authored weight table, and the labels largely encode that same table — so
"a learned model beats the formula on panel agreement" is close to tautological.
Switching away from the formula trades a transparent hand-authored rule for a model
that has learned that same rule, **with no independent evidence that either serves
users better**.

**The neural matcher ships because the project requires it** (ADR 0001), not because
it won anything. It did not win. Its honest standing against the alternatives is
reported in full below, with paired confidence intervals, and the requirement is
named as the reason it serves.

Nothing in this document authorises turning it on. That is DEV-99, and it is
reserved for a human.

---

## 1. What shipped

`data/models/matcher_nn_v1.json`, written by `data/scripts/export_nn_model.py`
(DEV-97). It is the first trained neural artifact this project has produced.

| field | value |
|---|---|
| `model_version` | `matcher-nn-v1` |
| `model_type` | `probability_averaged_mlp_ensemble` |
| Variant | `D5_ensemble_dropout_0.5_wd_1e-2`, selected by DEV-95 |
| `feature_version` | `features-v4` — 84 features (2·18 questions + 3·16 careers), 16 careers |
| `temperature` | `0.80` |
| `deployment.status` | `ranking_only` |
| `training.dataset_digest` | `2bdd5ec99d6a49a2a19c40163cf7a69d560453e3095bc6b4241c6065f18a4b27` |

**The exact configuration** — read from `selected_specification` in
`round2_results.json`, which `sweep_round2.py` generates from `inspect.signature`,
and rebuilt by the exporter from that record rather than retyped:

| field | value |
|---|---|
| class | `nn_model.SeedEnsemble` |
| `n_members` | 5 |
| member class | `nn_model.NNClassifier` |
| `hidden_sizes` | `[64, 32]` — so the trunk is 84 → 64 → 32 → 16 |
| `dropout` | 0.5 |
| `weight_decay` | 0.01 |
| `lr` / `optimizer` / `lr_schedule` / `momentum` | 0.001 / `adam` / `None` / 0.9 |
| `batch_size` / `max_epochs` / `patience` / `val_fraction` | 32 / 400 / 30 / 0.15 |
| `input_noise` | 0.0 |
| `member_seeds` | `random_state + i for i in range(n_members)` → 42, 43, 44, 45, 46 |
| `random_state` | 42 |

**This is five networks, not one, and that is a real cost rather than a detail.**
Serve-time inference runs five forward passes before averaging in probability, and
the artifact carries five full weight sets. One hyperparameter, `val_size`, postdates
DEV-95's record (DEV-96 added it); it is listed in `training.unrecorded_hyperparameters`
rather than absorbed silently, and the zero drift in §3 is the evidence it is inert.

**Attribution is integrated gradients over the logit of the mean probability** —
`log(mean_i softmax(z_i)) / T`, because that is the logit of the distribution actually
served, and the place `train_models.apply_temperature` fits `T`. Averaging the five
members' attributions would instead explain the mean of their *logits*, which is a
different function; `nn_rework_round2.md`'s closing note that "attribution over a
probability-averaged ensemble is the average of the members' attributions" predates
DEV-94 and is superseded by it.

---

## 2. The state it reaches, and the vocabulary gap this ticket had to close

`CONTEXT.md` defines four states — Qualified, Selected, Servable, Deployable — and
they were previously used interchangeably, which is why it defines them. `matcher_nn_v1`
exposed a fifth condition that none of them names.

- It is **Selected**: Gate 2's successor contest (Round 2) chose it.
- It is **Servable**: `matcher_nn.py` executes it with measured attribution.
- It is **not Qualified**: Qualified means "cleared Gate 1 — calibrated *and* stable".
  This model is stable and **not** calibrated.
- Therefore it is **not Deployable**, since Deployable is defined as "Qualified,
  Servable, and revalidated".

But ADR 0002 says a model failing the ECE half "may still ship as the *ranking*
source, with displayed percentages falling back to the formula's" — a real, intended
condition. **ADR 0002 splits the ship *floor*; it does not split the *state*.**
DEV-97 hit this, refused to resolve it by stretching "Deployable", and handed it here.

**Resolution: one new state is added to `CONTEXT.md`, `Ranking-Deployable`**, rather
than amending `Qualified` or `Deployable`. Amending either would retroactively change
what every earlier record meant by those words, which is the exact failure `CONTEXT.md`
exists to prevent. The new term is defined against the halves ADR 0002 already
distinguishes, and its machine-readable form is the `deployment.status: "ranking_only"`
string the artifact already carries — so the vocabulary word and the artifact field
are one concept, not two.

**The accurate sentence, and the only one this document asserts about deployability:**
*`matcher_nn_v1` is Ranking-Deployable. It may serve the ranking under ADR 0002's
mitigation, with displayed percentages falling back to the formula's. It is not
Deployable.*

Note also that `Incumbent` is defined as "the **Deployable** model currently
recommended as production default" — so `matcher_nn_v1` cannot become the Incumbent
by this route.

**The Incumbent is `matcher_logistic_v2.json`, the exported fixed-`C = 1.0` artifact —
not `logistic_tuned`.** These are two different models and the distinction is easy to
lose, so it is stated once here and honoured throughout. `logistic_tuned` is a *nested
evaluation protocol* that re-selects `C` in every outer fold (4.0, 4.0, 4.0, 0.05,
0.25); it has no single configuration, no artifact, and therefore cannot be Deployable,
which `Incumbent` requires. What is Deployable is the exported artifact: one fixed `C`,
revalidated post-export, clearing both floors. §5.1 compares the two artifacts; §4
reports effect sizes against `logistic_tuned`, which is the comparator the sweeps
measured and **not** the model that would actually be replaced — see disclosure 9 in §9.

Neither is *served*: `MATCHER_MODEL_PATH` is blank and production runs the formula.

---

## 3. The ship floor (ADR 0002)

Revalidated by the exporter on the **exact exported configuration**, at Gate 1's
convention of one fixed partition (seed 42), after `assert_deterministic` passed.
Source: `selection.exported_config_gate1` in the artifact.

| half | measured | floor | verdict | mitigable? |
|---|---|---|---|---|
| pooled OOF ECE (**mitigable**) | **0.13922660469462908** | ≤ 0.10 | **FAILS** | yes — ships as ranking source, percentages fall back to the formula |
| top-2 stability (**hard**) | **0.7345667591736047** | ≥ 0.60 | **CLEARS** | no — no mitigation exists |

**Both reproduce DEV-95's recorded ship floor at max drift exactly 0.** That is what
proves the artifact serialises the configuration that was evaluated, and it is a
stronger check than a signature audit: a silently changed default would move a digit.

### Both halves under all five experiment seeds

Reported beside the gated verdict, never substituted for it — switching the gate to a
five-seed mean after seeing the data would be moving a threshold rather than
tightening one. Source: `selection.ship_floor_across_seeds`.

| seed | ECE | clears ≤ 0.10? | top-2 stability | clears ≥ 0.60? |
|---|---|---|---|---|
| 42 (gated) | 0.1392 | **NO** | 0.7346 | yes |
| 43 | 0.1199 | **NO** | 0.7055 | yes |
| 44 | 0.1402 | **NO** | 0.7178 | yes |
| 45 | 0.0984 | yes | 0.7175 | yes |
| 46 | 0.1067 | **NO** | 0.7034 | yes |
| **summary** | mean 0.1209 ± 0.0168, max 0.1402 | **1 of 5** | mean 0.7158 ± 0.0111, min 0.7034 | **5 of 5** |

**Failing ECE is this configuration's common case, not the gated partition's
peculiarity.** Four of five partitions fail it. Round 1's modal Variant cleared on
four of five, so its gated failure genuinely was a partition effect; that defence is
not available here. The mitigation is what makes this model shippable, not an argument
that the number is unrepresentative.

### The mitigation, and where it is carried

The artifact has no bare `deployable: true` to misread. `deployment.status` is the
string `"ranking_only"`, `deployment.match_percent` reads `FALL BACK TO THE FORMULA`,
and a fourth entry joins `caveats` — which travel inside the artifact to
`RecommendationsResponse.model_caveats`, the persisted history jsonb, and `Results.jsx`.
**This model may serve the ranking; its percentages are not calibrated and must not be
displayed as if they were.**

---

## 4. How it stands against the alternatives

Pooled out-of-fold top-2 agreement, five experiment seeds, nested protocol. **The
sampling unit is the profile**: each profile's top-2 hit indicator is averaged across
the five seeds, then differenced, then 10,000 bootstrap resamples are drawn over the
232 profile ids. The intervals cover profile sampling variability *conditional on the
seeds drawn*; they do not fold in seed variability, which is why the per-seed table is
reported separately rather than summarised into them. Source: `nn_rework_round2.md`.

| comparison | δ (top-2) | 95% paired CI | CI excludes 0? | materiality \|δ\| ≥ 0.02 | sign holds | in profiles |
|---|---|---|---|---|---|---|
| vs `logistic_tuned` (nested comparator, **not** the Incumbent — §2) | **−0.0181** | [−0.0440, +0.0060] | no | **not cleared** | 4 of 5 seeds | 4.2 of 232 behind |
| vs `gbt_tuned` (the Gate-2 winner) | **−0.0440** | [−0.0750, −0.0138] | **yes** | **cleared** | 5 of 5 seeds | 10.2 of 232 behind |

The materiality marker is a **reporting standard, not a gate** (plan Step 2.5): under
ADR 0001 the neural matcher ships either way, so it sizes the gap rather than
authorising anything.

### Seed variance, reported rather than summarised

| seed | top-2 neural | top-2 `logistic_tuned` | top-2 `gbt_tuned` |
|---|---|---|---|
| 42 | 0.832 | 0.849 | 0.892 |
| 43 | 0.823 | 0.871 | 0.879 |
| 44 | 0.836 | 0.841 | 0.879 |
| 45 | 0.858 | 0.858 | 0.871 |
| 46 | 0.845 | 0.866 | 0.892 |
| **mean ± sd** | **0.839 ± 0.012** | **0.857 ± 0.011** | **0.883 ± 0.008** |

**Read together with §3, the pattern is consistent:** the neural matcher is behind on
agreement and behind on calibration, and ahead on stability. Stability is the one
thing it clearly wins, and it is not nothing — it is the property that says the same
user gets the same recommendation regardless of which resample trained the model.

### Why displacement is judged against the logistic line and not the Gate-2 winner

`gbt_tuned` won Gate 2 and **cannot serve**: `matcher_model.py` is linear-only with
exact attribution, which is an explicit scope decision, so gradient-boosted trees have
no serving path. Beating it therefore says nothing about whether the neural matcher is
better than the model it would actually replace. The implication, stated rather than
discovered: **a measurably better model sits on the shelf unservable.** That was
already true before DEV-23 began.

**One gap this leaves open, and no round closed it.** The δ above is against
`logistic_tuned` — the nested per-fold-`C` protocol. The model that would actually be
replaced is the Incumbent artifact `matcher_logistic_v2.json`, at a fixed `C = 1.0`.
**No round measured the neural matcher against that configuration**, so the honest
position is that this document reports the gap to the comparator the sweeps used and
cannot quote a paired gap to the artifact. The two are not interchangeable: on the
single-partition C-sensitivity measurement in `nn_rework.md`, `C = 1.0` scores top-2
0.8707 against `logistic_tuned`'s nested 0.849, so the fixed-`C` artifact is, if
anything, the *stronger* of the two — which would make the real gap wider, not
narrower. That is a different protocol and an unpaired one, so it is stated as a
direction and **no δ is computed from it**.

---

## 5. Old and new numbers, side by side

### 5.1 The two exported artifacts — the only exactly comparable pair

Both were revalidated post-export by their own exporter, on the same
`cv_oof_and_stability` protocol, the same partition (seed 42) and the same 232 rows.
This is the comparison the DEV-99 approver actually needs.

| | `matcher_logistic_v2.json` (Incumbent) | `matcher_nn_v1.json` (this ticket) |
|---|---|---|
| `model_type` | `multinomial_logistic_regression` | `probability_averaged_mlp_ensemble` |
| post-export ECE | **0.0341** — clears | **0.1392** — fails |
| post-export top-2 stability | 0.6375 — clears | **0.7346** — clears |
| `temperature` | 1.05 (**softens**) | 0.80 (**sharpens**) |
| `deployment.status` | absent — it is Deployable | `ranking_only` |
| attribution | exact linear, closed form | integrated gradients, ~11% of careers get none (§7) |
| parameters served | one weight matrix | five networks |

**The neural matcher is worse calibrated than the model it would replace, by a factor
of four, and consistently so.** Since ADR 0002's mitigation routes displayed
percentages back to the formula, switching would not improve the displayed
percentages — it would leave them exactly as they are today, by design.

One precision point, because it is easy to get backwards: the `logistic` row above is
the **fixed `C = 1.0`** configuration the artifact serialises, whose raw ECE is 0.0341.
Gate 2's `logistic_tuned` selects `C` per outer fold (4.0, 4.0, 4.0, 0.05, 0.25) and
its *raw* ECE is 0.103, which would itself fail the floor. Both are honest; they are
different configurations, and only the first one ships.

### 5.2 Gate 1, as recorded (`gate1_verdict.json`)

Single fixed partition, no confidence intervals — these are point estimates and
nothing here treats them otherwise.

| model | raw ECE | top-2 stability | Qualified? |
|---|---|---|---|
| `logistic` | 0.034099440082920096 | 0.637516702641587 | **yes** |
| `small_nn` (V0) | 0.06183095636038942 | 0.6153150375167026 | **yes** |
| `lightgbm` | 0.128155228434309 | 0.5566450817144618 | no — fails both |
| `small_nn`, reseeded | — | 0.6670161373214101 | reported, not gated |

### 5.3 Gate 2, and the DEV-91 calibration re-baseline

The re-baseline is the clearest old-vs-new in the deliverable. `ece_pooled_legacy` is
what the old protocol printed — one temperature fitted on the whole OOF pool and then
scored on that same pool. It is shown to size the defect; it is not a metric.
Source: `gate2_winner.json`, `model_selection.md`.

| model | top-2 | ECE raw | ECE **cross-fitted** (gating) | ECE pooled-T (legacy, old) |
|---|---|---|---|---|
| `gbt_tuned` | **0.892** | 0.135 | **0.040** | 0.047 |
| `logistic_tuned` | 0.849 | 0.103 | 0.061 | 0.103 |
| `small_nn` (soft targets) | 0.845 | 0.095 | 0.102 | 0.078 |
| `two_tower` | 0.763 | 0.062 | 0.081 | 0.086 |
| `residual_matcher` | 0.849 | 0.103 | 0.061 | 0.103 |

ADR 0004's own prediction was directionally wrong and is worth repeating here because
the intuition is so natural: fitting T on the evaluation pool is a *fitted minimum*,
not a measurement — but cross-fitting applies five per-fold constants, which can
absorb fold-specific miscalibration a single global constant cannot. On this data
cross-fitted ECE is **lower** for three of four models. The defensible claim is only
that the old number was never a held-out estimate, not that it flattered.

`residual_matcher` is numerically identical to `logistic_tuned` because its `alpha`
was 0 in all five folds, at which point it *is* logistic regression — see §5.4.

### 5.4 Round 1 against Round 2 — and the price of ADR 0003

| | Round 1 (DEV-93) | Round 2 (DEV-95) |
|---|---|---|
| selected | `C4_residual_matcher` — 23 of 25 contests | `D5_ensemble_dropout_0.5_wd_1e-2` — 7 of 25 |
| what it is | frozen logistic + gated MLP; **α = 0 in 18 of 25 folds**, i.e. exactly logistic regression | a genuine 5-member MLP ensemble |
| δ vs `logistic_tuned` | −0.0026 [−0.0095, +0.0043], sign 2 of 5 | −0.0181 [−0.0440, +0.0060], sign 4 of 5 |
| δ vs `gbt_tuned` | −0.0284 [−0.0595, +0.0026], sign 5 of 5 | −0.0440 [−0.0750, −0.0138], sign 5 of 5 |
| ship floor, gated | stability 0.655 ✓, ECE 0.122 ✗ | stability 0.735 ✓, ECE 0.139 ✗ |
| ECE across 5 seeds | clears **4 of 5** | clears **1 of 5** |

Round 1's result was negative and cleanly so: the twelve pure-MLP Variants were
selected **zero times between them**, and the pre-registered ADR 0003 rule ("α = 0 in
≥ 3 of 5 outer folds is *no non-linear signal found*") fired in four of five seeds,
disqualifying the Residual Matcher from being the shipped neural model.

**The cost of obeying that rule, priced on held-out top-2 and exactly paired** (both
rounds ran seeds 42–46 over the same fold partitions, so the per-profile indicators
line up row for row):

> δ (Round-2 selected − Round-1 selected) = **−0.0155**, 95% paired-bootstrap CI
> [−0.0388, +0.0060] over 10,000 resamples of 232 profile ids. **The CI includes
> zero.** Read as: obeying ADR 0003 costs 3.6 profiles out of 232 against the model
> Round 1 would have shipped.

This is *not* the two rounds presented as a series — the candidate sets differ. It is
the price of a candidate set that excludes the Residual Matcher, which is precisely
what ADR 0003 asks to be reported explicitly.

### 5.5 The plan's Step 6 outcome table, against what happened

Three of the five pre-registered rows fired at once, which is worth stating because
each was written as if it were the only one.

| pre-registered outcome | fired? | consequence as written |
|---|---|---|
| No NN clears the stability floor → **escalate** | no | 5 of 5 seeds clear it |
| NN clears floor, materially behind logistic | **partly** | it clears and is behind, but \|δ\| = 0.0181 does **not** clear the 0.02 materiality marker |
| Residual Matcher best but α = 0 in ≥ 3/5 → substitute | **yes** | Round 2 substituted; cost reported in §5.4 |
| `gbt_tuned` wins Gate 2 → NN ships, gbt unservable | **yes** | §4 |
| NN wins Gate 2 → NN ships | no | it did not win |

---

## 6. The learning curve (DEV-96) — would more data close the gap?

**Verdict: flat / inconclusive against both comparators.** The pre-registered reading
asks only whether the CI on Δgap = gap(n=232) − gap(n=80) excludes zero *in the
narrowing direction*, computed over the 80 profiles common to both points. Source:
`learning_curve.md`.

| comparator | Δgap | 95% paired CI | reading |
|---|---|---|---|
| `logistic_tuned` | −0.0425 | [−0.0975, +0.0125] | includes zero — **flat / inconclusive** |
| `gbt_tuned` | +0.0025 | [−0.0800, +0.0850] | includes zero — **flat / inconclusive** |

**"Flat" is not "no gap", and it is not "the gap is fixed".** Two separate readings
that are easy to run together:

- *There is a gap.* At n=232 it is +0.0302 [+0.0026, +0.0595] against `logistic_tuned`
  and +0.0466 [+0.0155, +0.0793] against `gbt_tuned` — both excluding zero.
- *More data plainly helps the model.* The neural matcher goes 0.635 → 0.820 top-2
  from n=80 to n=232, **+0.185**. But so do the comparators (`logistic_tuned` +0.125,
  `gbt_tuned` +0.206), which is why the *relative* standing does not move.
- An interval covering zero covers useful narrowing as well as none.

**Actionable reading: at these sizes, more labels of this kind are not measurably
closing the distance to the alternatives.** That is evidence against funding a bigger
dataset *for that purpose* — and it says nothing about the validity problem in §7,
which more labels of the same kind would not touch at all.

### The class-balance caveat that qualifies all of the above

**The main curve does not control class balance.** Class-floored stratified
subsampling gives every class at least 3 rows, which puts the max:min skew at 1.00 at
n=48 rising to **9.40** at n=232 — so balance and n move together at every point, and
the small-n points are *more* balanced than the large ones. An observed narrowing
could therefore be a balance effect rather than a data-size effect.

The two-point balance-controlled control curve is the attempt to separate them, and it
is **barred from carrying trend weight** (plan Step 2.6): two points cannot distinguish
a trend from a pair of draws, no CI is computed across them, and the two points do not
share profiles, so it is **not a paired comparison**. What it shows is a direction: the
gap is *wider* against both comparators when the classes are made uniform — the
opposite of the direction the plan warned might manufacture an apparent narrowing. It
is also partly a harder *measurement*, since balancing changes the test rows too.

Three further limits, stated because they are easy to assume away: n=48 is a protocol
floor (one training example per class after the validation rule) and is **excluded**
from the pre-registered test; every number is conditional on **one subsample draw** per
point; and the curve measures how one **frozen** configuration's gap moves with n, not
how the *selection* moves with n — so it does not settle whether Round 2's unstable
selection is a sample-size effect.

---

## 7. Validity — what none of these numbers can tell you

This section is the one that governs the DEV-99 approval.

### The labels are circular with the thing they are used to evaluate

Every gate metric in this deliverable is agreement with an **LLM panel**, not with
human practitioners. Its labeling is two-stage: a **deterministic stage 1** shortlists
careers from the `careers.json` bonus table, and an LLM **stage 2** picks within that
shortlist, prompted with the option→career key derived from the same table.

Measured from the raw vote log by `data/scripts/measure_circularity.py`, over the 711
error-free `panel-v2.1.0` votes that produced the 232 silver labels:

| reading | measured | what it means |
|---|---|---|
| stage-2 top-1 inside the stage-1 shortlist | **678 / 678 = 100.0%** | **structural, not evidence** — the prompt permits nothing else |
| stage-2 top-1 follows the tie-breaker key (any bonus rule) | **615 / 651 = 94.5%** | this is the "~94% of the time it speaks" every report quotes |
| the same, counting only primary (+3) rules | 516 / 651 = 79.3% | the strict reading; materially weaker, reported so the headline is not the only one |
| the consensus **label** follows the key | 206 / 217 = 94.9% | the vote-level rate carries to the thing models actually train on |

**Until this ticket the ~94% was a literal.** No script computed it — `panel_label_profiles.py`
computes the *different* 52.2% formula-vs-panel figure — and it sits inside `caveats`
in both exported artifacts, from where it reaches users. It is now computed, and
`data/scripts/tests/test_measure_circularity.py` pins the shipped caveat text against
the measurement, so regenerating the labels breaks the build instead of quietly
leaving every artifact asserting a stale rate.

Two related agreement figures, which measure different things and must not be run
together with the above: the questionnaire-only heuristic fit (the answer-key winner)
agrees with the panel consensus **52.2%** of the time, and the full production formula
(fit + sem + skill) top-1 agrees **46.1%** of the time.

### Panel self-consistency is not corroboration

The three personas share one base model (`qwen2.5:7b-instruct`) at temperatures
0.2 / 0.6 / 0.9. They are correlated, not independent raters, so their agreement is
**self-consistency**. For the shipped `panel-v2.1.0` labels, `synthetic_agreement_report.md`
records **Fleiss' κ = 0.857**, with pairwise Cohen's κ 0.843 / 0.853 / 0.875.

*Correction:* plan Step 4.1 and the DEV-98 ticket both state "κ ≈ 0.88–0.92". That
range matches no recorded figure in this tree — 0.930 was the rejected `panel-v1.0.1`
run whose personas were clones, and 0.864 was `panel-v1.1.0`. The correct value for the
labels that trained this model is 0.857. The caveat's direction is unchanged: a κ near
1.0 here would be a red flag for persona non-independence, not a quality guarantee.

### What the paired confidence intervals do and do not cover

Every CI in this document quantifies **sampling variability within a circular
dataset** and **inherits its bias entirely**. A tighter interval is not a better
estimate of recommendation quality; it is a better estimate of agreement with the
bonus table. No interval here can be narrowed into evidence about users.

### What a non-circular validation would require — scoped, not implemented

A **Gold Slice**: approximately 80–120 profiles labeled by **≥ 3 human practitioners
who did not author the bonus table**, stratified across all 16 careers. It does not
exist, and building it is not in DEV-23's scope. It is the only thing that would make
any agreement metric here mean recommendation quality.

**Two independent defects, and only one of them needs better labels.** Circularity is a
construct-validity problem: the metric measures the wrong thing. The calibration
fitting bug (ADR 0004) was a *statistical* problem: the metric was computed wrongly.
DEV-91 fixed the second and it never needed better labels — a Gold Slice would have
reproduced the same bug on better data. `CONTEXT.md` reserves **Leakage** for a third,
distinct thing, and none of the three is a synonym for the others.

---

## 8. Costs and open questions this document does not close

**Explainability has a measured hole.** Integrated-gradients attribution adapts its
step count 32 → 512 until the relative completeness residual clears 1e-3, and a career
that never clears it emits **no model-derived reasons** rather than numbers that do not
sum to what they claim. Measured on the real artifact by
`services/matching/tests/ig_diagnostics.py --artifact data/models/matcher_nn_v1.json`:

| sample | explanations | fell through | strict median residual | reached the 512 cap |
|---|---|---|---|---|
| real `matcher_nn_v1` | 640 | **75 = 11.7%** | 5.17e-4 | 146 |
| real `matcher_nn_v1`, 100 profiles | 1600 | **167 = 10.4%** | 5.13e-4 | 350 |

The mechanism is not a bug: the integrand jumps at every ReLU breakpoint, so the
midpoint Riemann sum is O(1/m) and beating it requires locating the breakpoints —
the analytic activation-pattern tracking plan Step 5.2 explicitly rejects. **It is a
real accuracy / latency / tolerance trade reserved for a human**, with three options:
raise the cap, which costs latency roughly linearly in `m`; loosen the tolerance, or
change what "relative" divides by (`Attribution.attribution_mass` is already carried,
and at that reading essentially nothing falls through); or accept the fall-through as
designed — "better silence than attributions that do not sum to what they claim".
DEV-94's synthetic 34–61% was pessimistic by roughly five times, so "a large minority
of careers" is no longer the right description — "about one in nine" is.

**The one figure that has *not* been re-measured on the real artifact is the latency.**
DEV-94 recorded ~66 ms per career explained, so ~200 ms per request at `TOP_N = 3` —
but that was the synthetic fixture, which reached the 512-step cap in 507 of 640
explanations against the real artifact's 146. Cost is roughly linear in the step count
actually taken, so the real figure should be materially lower and **nobody has measured
it**. The ~200 ms number should be read as an upper bound inherited from a harder
fixture, not as today's serving cost.

**16 of 36 question features are still discarded downstream.** `reason_builder.py:18`
defines `QUESTION_PHRASES` for q1–q10 only, and that dict is also the iteration set
(`:71`). The bank is 18 questions, and q11–q18 are the *pure discriminators* — zero
questionnaire weight, signal carried entirely by per-option bonuses, precisely the
features a learned model has most reason to lean on. This artifact computes their
attributions correctly and they are thrown away until **DEV-89** lands. DEV-89 is a
blocker of the serving *merge*, not of this document, and it degrades the
currently-served formula path right now.

**Serving cost.** Five forward passes per request instead of one matrix multiply, plus
the IG passes for the top-N explained careers.

---

## 9. Disclosures, counted rather than argued

1. **Which comparisons are paired, and which are not.**
   *Paired* (same folds, same seeds, per-profile indicators aligned): every δ and CI in
   §4, the Round-1-vs-Round-2 δ in §5.4, and every learning-curve gap and Δgap in §6.
   *Same protocol and partition but different estimators* (sizes a change, transfers no
   verdict): §5.1's artifact-vs-artifact table and §5.2's Gate-1 rows.
   *Not paired, no CI computed*: the control curve's two points in §6 — they share no
   profiles and change the test rows as well as the training rows — and the `C = 1.0`
   versus `logistic_tuned` direction noted at the end of §4.

   **The comparator in §4 is not the model that would be replaced.** Every δ is against
   `logistic_tuned`, the nested per-fold-`C` protocol; the Incumbent is the fixed
   `C = 1.0` artifact. No round measured the neural matcher against the artifact's
   configuration, so no paired gap to it exists in this deliverable. The available
   evidence points to that gap being **wider**, not narrower (§4).

2. **Effect sizes quoted without a CI, named.** Three, all from the selection metric
   rather than the reported one: the substitution cost over the best non-linear Variant
   (+0.0280 mean inner-CV top-2, worst contest +0.0702); the ensemble attribution
   D5 − D6 (+0.0237) and its Round-1 counterpart C3 − V0 (+0.0353). Gate 1 and Gate 2
   are single-partition point estimates and carry no intervals either. Everything in
   §4, §5.4 and §6 does carry one.

3. **The ECE failure is reported before the stability pass** — in §3's table, in §5.1's,
   and in the verdict sentence in §2. It is not a footnote to a headline pass.

4. **The neural matcher was tuned harder than either comparator, after Round 2.** Round 1's
   14 Variants plus Round 2's 6 is 20 configurations, against `gbt_tuned`'s 16-point
   nested grid and `logistic_tuned`'s 4. "The NN was not tuned harder than the
   alternatives" was true after Round 1 and is **no longer true**. The search budget was
   fixed in advance so that "keep tuning until it wins" was unavailable, and it is now
   spent: **there is no Round 3.**

5. **The selection did not converge.** `D5` took 7 of 25 contests (28%); **8 different
   Variants** won contests; the top count was a **tie** with `D2_ensemble_dropout_0.5`,
   resolved on mean inner-CV top-2. Registry order (an earlier-declared Variant wins
   exact ties) decided **5 of 25** contests, and `D5` appears in tied groups, so the
   record cannot distinguish a tie-broken pick from a decisive one for those. Read `D5`
   as the modal answer of an unstable selection, not a configuration the evidence
   singled out. Both arms of the tie reach the same ship-floor verdict, so the tie-break
   moved *which* configuration ships, not *whether* one could.

6. **Round 1's contest was biased toward its own winner.** The Residual Matcher entered
   carrying a score that was a maximum over its four-point `alpha` grid on the ranking
   metric itself, while every other Variant contributed a single draw. That is not
   Leakage — no held-out row was touched — but it cost the contest fairness between
   Variants. It does not change the finding's direction: the Residual Matcher won mostly
   *at α = 0*, so the extra freedom it enjoyed was the freedom to switch its neural
   branch off.

7. **The ~94% was never computed before this ticket**, and the plan's Fleiss κ range
   was wrong. Both are corrected in §7 from the recorded sources.

8. **Not measured anywhere in DEV-23:** whether either the formula or any learned model
   produces better career recommendations for a real person. No experiment in this
   deliverable bears on it.

---

## 10. What this document authorises

**Nothing.** It is the input to an approval, not the approval.

- **DEV-99** — flipping `MATCHER_MODEL_PATH` — requires a human who has read §7. The
  variable is blank in `.env.example`, defaults blank in `docker-compose.yml`, and
  production runs the formula. (`backend/.env:23` points at the stale
  `matcher_logistic_v1.json`, which is `features-v1`, correctly refused on load, and
  never reaches the services anyway — compose reads the root `.env`.)
- **The honest grounds for switching**, restated after DEV-95 corrected them: the
  ADR 0001 project requirement, better recommendation stability (0.735 vs 0.6375 — the
  one thing the neural matcher clearly wins), and maintainability. **Not calibration**
  (it is four times worse, and the mitigation routes percentages back to the formula
  anyway) and **not accuracy** (behind on the same silver labels).
- **DEV-89** must merge first. Shipping this artifact before it means computing
  integrated-gradients attributions correctly and discarding them for 44% of the
  question-feature surface.
- Both flipping the flag and *not* flipping it are defensible on this evidence. What is
  not defensible is claiming the evidence chose.
