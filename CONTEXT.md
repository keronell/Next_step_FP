# The Next Step

A career-discovery app: a questionnaire and an optional self-described profile are matched against a catalog of careers, and the chosen career opens a learning roadmap the user works through.

This file is also the vocabulary for how candidate scoring models are evaluated before any of them is allowed to serve that ranking — the Scoring, Labels, Evaluation and Selection sections below came from the DEV-23 matcher rework.

## Language

### Identity

**Role**:
What an account is allowed to do — `user` or `admin`. Never an occupation; that is a Career.
_Avoid_: permission, access level

**Admin**:
An account holding the admin role. The only account that can see every account and delete one. Granted in the database, never through the app.
_Avoid_: superuser, moderator, staff

### Matching

**Career**:
One of the 16 occupations a user can be matched to and shown a roadmap for.
_Avoid_: job, field, role (reserved for the authorization sense)

**Assessment**:
One completed run of the questionnaire, producing a ranked set of career recommendations.
_Avoid_: quiz, test, submission

**Recommendation**:
One of the three careers an assessment matches a user to.
_Avoid_: result, suggestion, match

**Profile**:
What a user says about themselves — experience, projects and skills — offered between the assessment and the results. Optional, and English-only.
_Avoid_: CV, resume, bio

**Skill gap**:
A skill a career wants that the user's profile does not evidence.
_Avoid_: missing skill, weakness

### Roadmap

**Roadmap**:
The ordered learning path for one career, made of stages.

**Unlocked**:
A roadmap is unlocked for a user when they hold a recommendation for its career — only an unlocked roadmap can be opened.
_Avoid_: gated, entitled, permitted

**Stage**:
A named, ordered group of nodes within a roadmap — "Foundations", "Gives an Advantage". Nodes within a stage are in learning order; the job-ad stages are the exception, ranked by demand rather than sequenced. Serialized as `sections` on the wire, and referred to as a stage everywhere else.
_Avoid_: section, column, phase

**Node**:
One skill on a roadmap, shown as a card the user can open and mark complete.
_Avoid_: item, topic, card

**Status**:
Which of three states a node is in for this user: not started, skill gap, or completed. Completion is the only state the user sets directly.
_Avoid_: progress, state

**Market frame**:
The badge and frame drawn around a node whose skill was derived from real job ads, marking it as in demand or an advantage.
_Avoid_: demand badge, job-ad node

**Spine**:
The vertical gold thread running down the canvas, joining every stage in order.

**Rail**:
The dotted horizontal line above one row of nodes, from which each node hangs.
_Avoid_: trunk

**Drop**:
A short gold connector on the spine — from a stage header down to its rail, or from one stage to the next.
_Avoid_: stub, connector

### Scoring

**Formula**:
The hand-authored weighted blend of questionnaire fit, semantic similarity, and
skill overlap that currently produces every served recommendation.
_Avoid_: heuristic, baseline, rules engine

**Learned Matcher**:
A trained model that replaces the Formula's scoring step, consuming the same
feature vector and emitting the same response shape.
_Avoid_: the model, the NN, ML matcher

**Answer Key**:
The career ranking implied directly by the `careers.json` bonus table for a given
set of answers. The thing the Formula encodes and the labels largely reproduce.

**Residual Matcher**:
A Learned Matcher whose logits are a frozen logistic solution plus a gated
non-linear correction, so it collapses to exactly logistic when the gate is zero.
_Avoid_: C4, hybrid model, linear+MLP

### Labels and their limits

**Panel**:
The ensemble of LLM judgments that assigns a career ranking to a synthetic
profile. Its agreement with itself is self-consistency, never corroboration.
_Avoid_: annotators, judges, raters

**Silver Label**:
A Panel-assigned career ranking used as training and evaluation ground truth, in
the absence of human-assigned labels.
_Avoid_: ground truth, gold label, target

**Gold Slice**:
A hypothetical set of profiles labeled by human practitioners who did not author
the bonus table. Does not exist; the only thing that would make agreement metrics
mean recommendation quality.

**Circularity**:
The property that Silver Labels reproduce the Answer Key, so agreement with them
measures fidelity to a hand-authored table rather than real-world quality.
_Avoid_: bias, contamination, leakage (leakage means something else here)

### Evaluation

**Gate 1**:
The existential admission check on a Learned Matcher: calibration (pooled
out-of-fold ECE) and recommendation stability (top-2 set agreement across
resampled sub-models). Deliberately not a comparison against the Formula.

**Gate 2**:
The selection contest among Learned Matchers that cleared Gate 1, decided on
pooled out-of-fold top-2 agreement with calibration as tiebreak.

**Variant**:
One fully-specified Learned Matcher configuration entered into the sweep.
Distinct from a hyperparameter setting explored inside a fold.

**Leakage**:
Any path by which data used to score a model influenced that model's selection
or fitting. Reserved for this; never used for Circularity.

**Feature Version**:
The identifier of the feature vector layout. A model artifact whose Feature
Version differs from the serving code is refused at load rather than adapted.

### Selection and shipping

These are distinct and were previously used interchangeably. The first four are
evaluated in that order, and none of them implies any of the earlier ones.
**Deployable** and **Ranking-Deployable** are the two terminal states, and they are
mutually exclusive — a model is in at most one of them.

**Qualified**:
Cleared Gate 1 — calibrated and stable. A property of one exact configuration,
never of an architecture, and never inherited by a reconfigured model.

**Selected**:
Chosen by Gate 2 as the best-scoring candidate. A purely statistical verdict that
knows nothing about whether the model can be served.

**Servable**:
An implementation exists that can execute the artifact at serve time with exact
or tolerance-tested attribution. A property of the serving code, not the model.

**Deployable**:
Qualified, Servable, and revalidated against the Gate 1 thresholds *after* export
in its exact shipped configuration. The only state that permits serving both the
ranking and the displayed percentages.

**Ranking-Deployable**:
Servable, and revalidated after export to clear the **hard** half of the Ship Floor
(top-2 stability) while failing the **mitigable** half (ECE). Permits serving the
*selection only* — which careers appear — with `matchPercent`, `score` and
`score_breakdown` all falling back to the Formula's, which also **orders** the
selected set, per [ADR 0005](./docs/adr/0005-gate-1-is-a-ship-floor.md). Its
machine-readable form is the artifact's `deployment.status: "ranking_only"`; the
field name predates the amendment and is kept for compatibility with shipped
artifacts, so the string says *ranking* where the meaning is *selection*.
Such a model is **not Qualified** — Gate 1 is calibrated *and* stable — and therefore
**not Deployable**; this is a separate terminus, never a weaker Deployable, and it can
never make a model the Incumbent. ADR 0005 splits the Ship Floor, not the state; this
term is what closes that gap (DEV-98).
`matcher_nn_v1.json` is Ranking-Deployable and, since DEV-99 (2026-08-04), is the
model actually served.
_Avoid_: partly deployable, deployable with caveats, conditionally deployable

**Ship Floor**:
The properties a model must have to serve at all, independent of how it ranks
against alternatives. Distinct from a kill criterion, which presumes abandoning
the model is possible.

**Incumbent**:
The Deployable model currently recommended as production default. Displacing it
is a decision with cost; tying with it is not a reason to switch.
