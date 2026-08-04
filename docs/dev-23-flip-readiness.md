# DEV-99 — flip readiness: what is verified, and the one thing that is not built

DEV-99. Companion to [`dev-23-nn-decision.md`](./dev-23-nn-decision.md), which is the
*evidence* input to the approval; this is the *mechanism* input. Vocabulary is
[`CONTEXT.md`](../CONTEXT.md)'s.

**Nothing here flips anything.** `MATCHER_MODEL_PATH` is untouched — blank in
`.env.example:15`, blank by default in `docker-compose.yml:56`, and blank in the
repo-root `.env` that compose actually interpolates. Production runs the formula.

Every claim below was produced by running the real `main.lifespan` and the real
scoring path, not by reading source. The reproducible form of each is
`services/matching/tests/test_flip_readiness.py`.

---

## The finding, which changes what DEV-99 is asking

**ADR 0005's mitigation is documented in three places and implemented in none.**
If the flag were flipped to the neural artifact today, the service would display the
model's uncalibrated percentages — the exact thing the artifact's own caveat tells
consumers not to do.

`matcher_nn_v1` is **Ranking-Deployable**, and `CONTEXT.md` defines that state as
permitting the ranking *"with displayed `matchPercent` falling back to the Formula's,
per ADR 0005"*. That fallback does not exist in code. So the state the model is in is
not a state the serving path can currently honour.

### What the artifact declares

```
$ python -c "import json; print(json.load(open('data/models/matcher_nn_v1.json'))['deployment'])"
{'status': 'ranking_only',
 'ranking': 'this model',
 'match_percent': "FALL BACK TO THE FORMULA - this model's percentages are uncalibrated",
 'mitigation_applied': 'ADR 0005 mitigable-ECE branch: ships as the ranking source only'}
```

Its fourth caveat says the same in prose, and that caveat *does* reach the response,
the persisted history and `Results.jsx`. **The warning arrives; the behaviour it
describes does not.**

### The three pieces of evidence

1. **The serving contract cannot express it.** `services/matching/app/services/matcher.py`
   declares the `Matcher` protocol with `feature_names` (:38), `version` (:40),
   `caveats` (:42), `predict_proba` (:44) and `contributions` (:48). There is no
   `deployment` member. Both implementations — `MatcherModel.__init__` and
   `NeuralMatcher.__init__` — read the artifact key by key and never touch
   `deployment`, so the block is discarded at load.

2. **The percentage is the model's probability, unconditionally.**
   `matching_service.py:323`, on the model path:

   ```python
   "matchPercent": round(probs[cid] * 100),
   ```

   There is no branch. The formula's percentage is computed at
   `matching_service.py:399` — inside `_match_formula`, which does not run when the
   model scores.

3. **No serving code reads the declaration.** Ripgrep for `deployment`,
   `ranking_only` and `match_percent` over `services/` and `frontend/src/` returns,
   outside the artifact JSON: a roadmap node id, a career description, and — since
   this ticket — the tests below that exist precisely to record the gap. Nothing
   under `services/*/app/` or `frontend/src/pages/`.

   *(Stated as "appears nowhere" in this document's first draft, which its own test
   file then falsified. Corrected here rather than left standing: it is the same
   right-conclusion-from-a-false-premise shape as the compose-scope wording
   corrected below.)*

### How big the substitution would be

Same request, same candidates, two scorers. 200 randomised answer sets over the full
18-question bank:

| top-1 `matchPercent` | mean | min | max |
|---|---|---|---|
| formula (what ADR 0005 says to display) | 73.3 | 60 | 85 |
| `matcher_nn_v1` (what is displayed today) | **58.0** | 26 | 85 |
| `matcher_logistic_v2` | 76.4 | 35 | 99 |

*Disclosure, counted rather than argued.* Candidates come from
`tests/conftest.make_candidates()`, whose `semantic_similarity` and `market_skills` are
canned — `chromadb` is absent from `backend/venv`, so the real RAG store cannot be
driven here. Two separate things ride on that, and only one of them is testable from
here:

- **The answer-set draw is not doing the work.** Re-run under four further seeds, the
  formula-minus-model gap is **mean 14.7 points, min 12.6, max 16.7** (against the
  headline seed's 15.3). The gap is a property of the two scorers, not of the sample.
- **The canned RAG signals remain a disclosure, not a measurement.** They cannot be
  varied without `chromadb`, so nothing here rules out the real store shifting the
  absolute levels. What it would have to shift is a ~15-point gap in the same direction
  under five independent draws.

Specific careers and ranking-agreement rates between scorers *are* fixture-dependent —
the fixture's canned semantic similarities dominate the formula — so the diagnostic does
not compute them and they are quoted nowhere in this document.

### A second surface, easy to miss

`matchPercent` reaches the UI in **two** places: `Results.jsx:96` (the animated bar)
and `History.jsx:187` (the saved-submission row). `model_caveats` is rendered in
**one** — `Results.jsx:43`. So an uncalibrated percentage persisted into a history row
is re-displayed on every later visit **with no caveat beside it at all**, and
persisted recommendations are stored as opaque dicts
(`SubmissionHistoryItem.recommendations: list[dict]`, `common/models/auth.py:65`),
so nothing rewrites them later. See the rollback limit below.

---

## What the mitigation costs, designed rather than assumed

The cheap reading — "one branch on `matchPercent`" — is wrong. ADR 0005 asks for the
**model to supply the ranking while the formula supplies the displayed number**, which
means both must be computed for the same request, and they currently live on two
mutually exclusive branches.

**Shape.** `Matcher` gains a way to answer "may I display my own percentages?"
(`deployment`, or a narrower boolean derived from it), defaulting to *yes* when the
artifact has no `deployment` block — `matcher_logistic_v2.json` has none and is
Deployable, so silence must keep meaning the current behaviour. Both implementations
supply it. `_match_model` then asks, and where the answer is no, substitutes formula
percentages for its own.

**Four problems that are not incidental:**

1. **`_match_formula` returns only its own `TOP_N`.** The model's top-3 need not be the
   formula's top-3, so for a career the model ranked and the formula did not, no
   formula percentage is computed anywhere. The per-career scoring loop has to be
   extracted from `_match_formula` and made callable for an arbitrary career set. This
   is the bulk of the work and it is why the fix is not a line.

2. **The displayed percentages stop being monotonic in the displayed order.** The model
   ranks A > B > C; the formula may score B above A. The UI would show *"1. A 55%,
   2. B 71%"*. `Results.jsx` animates a bar per rank and `History.jsx` prints the top
   row's percentage as a headline. **ADR 0005 does not address this**, and it is a
   product decision, not an implementation detail. The dishonest resolution — keep the
   model's order but reassign the formula's percentages sorted descending — produces
   numbers that belong to no career and should be rejected explicitly.

3. **`score` and `matchPercent` come apart.** Both currently derive from the same
   number, and `test_matching_with_model.py:48` asserts `matchPercent == round(score *
   100)` for one rec of one fixture. If `score` stays the model's probability (it is the
   ranking key, and provenance) that relationship breaks wholesale and that test must
   change deliberately. Note the two are *already* not identical — `score` is
   `round(prob, 3)` and `matchPercent` is `round(prob * 100)`, which disagree for
   **33 of 600** recommendations (5.5%) on the diagnostic's fixture purely by rounding.
   Any invariant written on `score` rather than on the probability itself will fire for
   reasons unrelated to the mitigation; the test below compares against the unrounded
   probability for exactly this reason.

4. **Which formula?** `_match_formula` switches to `PROFILE_WEIGHTS` when the user's
   profile yields skills. "The formula's percentage" has to mean the formula's own
   rule, profile branch included, or it is not the formula's percentage.

**Cost:** a small ticket, not a line and not an epic — protocol member, two
implementations, one extraction refactor in `matching_service`, the frontend/product
call on problem 2, and tests. Problem 2 is the only part that needs a human.

**What I did not do, and why.** I did not implement it. Two of the four problems are
decisions rather than code — the non-monotonic display, and whether ADR 0005's
mitigation is still the right one now that its consequence is visible. Choosing either
silently would be exactly the "quietly redefine the mitigation to something easier"
failure. If a different mitigation is preferred (suppress the percentage for
`ranking_only` models; display a band rather than a number), **that is an amendment to
ADR 0005 and belongs to the same human who decides the flip.**

The gap is pinned by two `xfail(strict=True)` tests in `test_flip_readiness.py` — they
fail today, and turn into a loud `XPASS` failure the moment the mitigation lands, so
whoever implements it is told to delete the markers. They deliberately do **not** assert
the current behaviour as correct: pinning `matchPercent == round(probability * 100)`
would turn the defect into a specification.

---

## The acceptance criteria that ARE satisfied, proved by running

### A failed artifact load still falls back to the formula — **verified**

Four failure modes driven through the real lifespan, each then scored through the real
matching path:

| `MATCHER_MODEL_PATH` | lifespan result | served output |
|---|---|---|
| blank (production today) | `None`, logs *"MATCHER_MODEL_PATH unset"* | formula |
| `matcher_logistic_v1.json` (stale, `features-v1`) | `None`, logs *"feature_version 'features-v1' != code 'features-v4'"* | **identical to formula** |
| nonexistent path | `None`, logs *"model artifact not found"* | **identical to formula** |
| structurally valid, unknown `model_type` | `None` | **identical to formula** |

Identity is asserted on the whole response, not just that a fallback occurred: a
fallback that engaged but left `model_version` or `model_caveats` stamped would still
pass a weaker check, and would tell a user their result came from a model that never
scored it.

### The service logs the loaded model version — **verified**

`Learned matcher loaded: matcher-logistic-v2` / `matcher-nn-v1`, from
`main.py:47`. Asserted for both artifacts. This is the operator's only confirmation
that a flip took effect.

### Rollback: clearing the variable restores the formula with no redeploy — **verified, with one limit**

Proved in a single process with no module reload — only the setting changes. The
artifact is read once in the lifespan and reached only through `app.state`, so a
restart with the variable cleared is a complete rollback of the *scoring path*.

**The limit, which is not a defect but is not restored either:** `model_version` and
`model_caveats` are embedded per recommendation and persisted verbatim. Clearing the
variable changes what **new** submissions are scored with; it rewrites nothing already
in the state store. A user's history stays permanently mixed, and — per the second
surface noted above — `History.jsx` re-renders each stored `matchPercent` with no
caveat of its own. Rollback is complete forward, not backward.

### Model version and caveats propagate end-to-end — **verified**

The chain is:

`matching` embeds per-rec → `questionnaire/app/routes/questionnaire.py:41` derives the
response-level `model_caveats` from `recommendations[0]` → `save_submission` publishes
the recs verbatim → history stores them as opaque dicts → `Results.jsx:43` renders them.

`test_matching_with_model.py:146` (DEV-97) already carried the **real** artifact's
caveats to `/internal/match`. It stops there, because that is where its service's
responsibility ends — so nothing asserted that a genuine artifact's caveats survived the
hop into the questionnaire response, whose own test used hand-written strings
(`test_questionnaire.py:69`). This ticket closes it:
`test_the_real_artifacts_caveats_survive_the_response_and_reach_persistence` reads the
shipped artifact's caveats and asserts those exact strings arrive both in
`RecommendationsResponse.model_caveats` and in the per-rec payload handed to
persistence. The caveats are prose containing punctuation and a non-ASCII character, so
"a list of strings arrived" and "these strings arrived" are not the same assurance.

---

## Environments the flag would be set in, and each blast radius

| where | value today | who reads it | blast radius if flipped |
|---|---|---|---|
| repo-root `.env` (gitignored) | **blank** | `docker-compose.yml:56` interpolation | **the whole compose stack** — this is the real production switch. Needs a *container* path (`/store/models/...`; `data/models` is mounted read-only at `/store/models`). |
| `.env.example:15` | blank | nobody at runtime | documentation only, but it is what the next person copies |
| `backend/.env:23` | `../data/models/matcher_logistic_v1.json` | the `dapr run` / local-uvicorn flow | **inert for compose**, and doubly safe — see below |
| `docker-compose.yml:56` | `${MATCHER_MODEL_PATH:-}` | compose | the default; changing it would hardcode a flip |

**One correction to the repo's own wording.** Several docs say backend/.env's
`MATCHER_MODEL_PATH` "never reaches the services". Measured with
`docker compose config`, it reaches **two** of them:

```
auth       MATCHER_MODEL_PATH='../data/models/matcher_logistic_v1.json'
matching   MATCHER_MODEL_PATH=''
roadmap    MATCHER_MODEL_PATH='../data/models/matcher_logistic_v1.json'
```

`auth` and `roadmap` pick it up through `env_file: ./backend/.env` and ignore it —
`matcher_model_path` is on the shared `common/config.py:22` settings object, but only
`services/matching/app/main.py:44` reads it. `matching` is the one service that would
act on it, and there compose's `environment:` key overrides `env_file:`, resolving to
`''`. So the conclusion the docs draw is right — **it never reaches the service that
uses it** — but the literal sentence is not. The stale artifact is refused on load in
any case (`test_the_artifact_backend_env_points_at_is_still_refused`), so the safety
argument holds twice over.

`README.md:206` lists `MATCHER_MODEL_PATH` among `backend/.env`'s keys for "services
(via `env_file`)", which is technically accurate and misleading in the same breath.

---

## A number DEV-89 did not have: what it costs on the artifact that would ship

DEV-89 (q11–q18 reason rendering) is a **hard prerequisite of merging** the NN serving
work. It is normally sized by feature count: `reason_builder.py:18` defines
`QUESTION_PHRASES` for q1–q10 only and that dict is also the iteration set (`:71`), so
**16 of 36 question features (44.4%)** are discarded. Both figures reproduce.

Feature count understates it. Measured on `matcher_nn_v1` itself — 300 explanations,
100 randomised answer sets over the full bank, positive attribution only (negative
attribution is never renderable for any question, so counting it would inflate the gap):

| | |
|---|---|
| renderable share of positive question-feature attribution, mean | **0.293** |
| the same, median | 0.158 |
| **discarded share, mean** | **0.707** |
| explanations where the *majority* of question mass is discarded | **248 / 300 = 82.7%** |

**About 71% of the question-feature attribution the model actually produces is thrown
away before it reaches a sentence** — not 44%. This is the quantitative form of
DEV-98's qualitative prediction that q11–q18 are "precisely the features a learned
model has most reason to lean on": they carry zero questionnaire weight and signal only
through per-option bonuses, so they discriminate, and the model leans on them hard.

(Same fixture disclosure as above. The question-feature attributions are the model's
own; the fixture affects only which three careers are explained.)

---

## What would make a flip coherent

Ordered, with owners:

1. **Decide the ADR 0005 mitigation** — implement it as written (accepting the
   non-monotonic display), or amend the ADR. **Human.** Without this the flip ships
   uncalibrated percentages regardless of who approved it.
2. **DEV-89.** Own ticket, own branch off `main`. Merge blocker; ~71% of the model's
   question attribution is discarded until it lands, and it degrades the
   currently-served formula path today.
3. **The approval itself** — a human who has read `dev-23-nn-decision.md` §7.
4. Set the repo-root `.env` to the **container** path, restart `matching` and
   `matching-dapr` **together** (shared netns), and confirm the
   `Learned matcher loaded: matcher-nn-v1` log line.

Items 1 and 2 are prerequisites of item 3 being *meaningful*, not just of item 4 being
safe. Approving a flip whose displayed percentages contradict the artifact's own caveat
is approving something other than what ADR 0005 describes.

## Recommendation

**Do not flip yet, and the reason is mechanical rather than evidential.**

The evidential case was settled by DEV-98 and it is genuinely balanced: both flipping
and not flipping are defensible, the neural matcher wins on stability and loses on
calibration and agreement, and ADR 0004 requires it to ship eventually. Nothing found
here moves that balance.

What this ticket found is that the flip as currently implementable is **not the thing
ADR 0005 authorised**. The model is Ranking-Deployable; the serving path can only
deploy it as if it were Deployable. Until the mitigation exists, "approve the flip" and
"ship uncalibrated percentages" are the same action, and the approver would be agreeing
to something the decision document explicitly says is not on offer.

The three mechanical criteria DEV-99 asks about — load-failure fallback, version
logging, rollback — are all satisfied and now tested. The blast radius is small and the
degradation paths are sound. It is a good switch; it is wired to the wrong thing.

---

## Closed: the mitigation was built (2026-08-04)

The gap this document reports is fixed. **The finding above is left standing as written**
— it is the record of what was true on 2026-08-03, and rewriting it would erase the
reason the work happened.

What changed since:

- `Matcher` gained a `deployment` member; both implementations parse the block at load
  through the shared `parse_deployment`, and an unrecognised `status` is a load failure
  rather than a permissive default.
- `_formula_scored` was extracted from `_match_formula`, which is what made the
  "four problems that are not incidental" tractable: problem 1 (a model-ranked career
  with no formula percentage) is solved by scoring every candidate before truncating,
  and problem 4 (which formula) by reusing the real one, profile branch included.
- Problem 2 — the non-monotonic display — was **answered by a human, not by code**:
  the model's selected set is ordered by the formula's percentage, so the top row always
  carries the highest one. That narrows what a `ranking_only` model supplies from the
  *ranking* to the *selection*, which is an amendment to ADR 0005 and is recorded there.
  The "dishonest resolution" this document warned against was rejected explicitly, along
  with a clamping variant that has the same defect more quietly.
- Problem 3 — `score` and `matchPercent` coming apart — resolved by making both the
  formula's, with the model's probability preserved as
  `score_breakdown.model_probability` so the selection stays auditable.

The two `xfail(strict=True)` tests did exactly their job: they turned into a loud
`XPASS` the moment the mitigation landed, and the markers were removed as instructed.
The second one is now stated in its **positive** form — equality with the formula's
percentage — which this document correctly said was not yet expressible.

**`MATCHER_MODEL_PATH` is still blank and the flip is still DEV-99's**, needing its own
human approval. This work removes the incoherence that blocked that approval; it does
not grant it.

---

## Closed: the flip happened (2026-08-04)

Approval was given by the human who owns the decision, after the two prerequisites this
document ordered had merged — the ADR 0005 mitigation (PR #37) and DEV-89 (PR #36). The
repo-root `.env` now reads `MATCHER_MODEL_PATH=/store/models/matcher_nn_v1.json` and the
neural matcher serves. `.env.example` and the `docker-compose.yml` comment name the same
value; the compose **default** stays `${MATCHER_MODEL_PATH:-}` deliberately, so blanking
one line is still a complete rollback.

Everything below was produced against the running 13-container stack with the real RAG
store (1853 job ads), not from the fixture this document had to use above.

### The finding this ticket did not predict: a restart is not always enough

The first restart with the flag set logged:

```
WARNING [app.main] Matcher model unavailable, using formula:
    malformed model artifact /store/models/matcher_nn_v1.json: 'coef'
```

`'coef'` is the **linear** loader's missing key. The running image had been built before
DEV-88, so it contained `matcher_model.py` and no `matcher.py` — no dispatch seam, and
therefore no `probability_averaged_mlp_ensemble` entry to dispatch to. The flag was set
correctly and the artifact was fine; the *image* predated the model family.

This is worth naming because of how it fails. The fallback behaved exactly as designed —
the service came up on the formula and served correct results — so nothing was broken,
and the only evidence of a no-op flip was one WARNING line whose text points at the
artifact rather than at the build. **`docker compose restart` cannot flip this flag on a
stale image; `up -d --build` can.** Step 4 of "What would make a flip coherent" above
said "restart", and that was incomplete.

### The five acceptance criteria, verified against the live stack

| AC | evidence |
|---|---|
| Human approval | given 2026-08-04, recorded on DEV-99 |
| Flag set, environments named | `docker compose config` resolves `matching` to `/store/models/matcher_nn_v1.json`; `auth` and `roadmap` still show `backend/.env`'s stale value and still ignore it |
| Service logs the version; failed load falls back | `INFO [app.main] Learned matcher loaded: matcher-nn-v1`, and the stale-image episode above is an unplanned live proof of the fallback |
| Caveats and version propagate end-to-end | a real submit returns 4 caveats and `model_version: matcher-nn-v1`; the persisted redis hash `sub:<id>` carries both verbatim |
| Rollback documented | **drilled, not just documented** — see below |

### The rollback drill

Blanked the line, `up -d matching matching-dapr`, and the service logged
*"MATCHER_MODEL_PATH unset — matching uses the deterministic formula"*. A real submit then
returned `model_version: formula-v1`, zero caveats and no `model_probability`. Restoring
the line and restarting brought `matcher-nn-v1` back. No image was rebuilt between those
three states, so the rollback claim — no code redeploy — is now exercised rather than
asserted.

**Two operational notes the drill surfaced.** Restarting `matching` + `matching-dapr`
leaves a window of roughly 15–30 seconds in which `questionnaire`'s Dapr invoke fails and
the gateway answers **503**; the SPA degrades to its offline estimate for that window, so
this is a visible blip rather than an outage, but it is not zero-downtime. And the
rollback limit this document already recorded held exactly as described: submissions
persisted while the model was serving still carry `matcher-nn-v1` and its caveats.

### What actually changed for users

The mitigation makes the flip much narrower than the raw scorer comparison above
suggests. On a fixed all-zero answer set through the real stack:

| rank | formula | neural matcher |
|---|---|---|
| 1 | UX Designer — 71% | UX Designer — **71%** |
| 2 | Frontend Developer — 67% | Frontend Developer — **67%** |
| 3 | Mobile Developer — 59% | Product Manager — 51% |

Identical numbers where the selections agree, because every displayed number is the
formula's either way. **The flip changes which careers are shortlisted, not the
percentages beside them** — which is what ADR 0005's mitigation is for, and it is the
concrete form of the ~15-point scale gap measured above no longer reaching a user.

Note the model's own ordering is *not* what is displayed: its highest probability in
that response was UX Designer at 0.353, but in a separate fixture run its top pick by
probability (devops, 0.765) displayed **second** at 24% behind product-manager at 42%.
The formula ranks within the model's shortlist, per the ADR amendment.

### Also done here

The artifact's fourth caveat was reworded. It said displayed percentages *"should fall
back to the formula's"* — an instruction to code that did not exist when it was written
and did by the time it shipped, and it renders to every user at `Results.jsx:43`. It now
describes the behaviour and says **SELECTION** rather than RANKING. Fixed at the source
(`export_nn_model.py::calibration_caveat`) and regenerated into the artifact through that
function, so a future re-export reproduces it; one line of the artifact changed and no
weight moved. `test_the_calibration_caveat_appears_only_when_ece_fails` asserted the
imperative `"FALL BACK"` and now asserts the caveat names the formula and the selection —
the test's intent was always "name the mitigation, don't just flag a problem", and only
its mood changed.

**Still open, and still not this ticket's:** the IG step-cap trade (~1 in 9 careers get no
model-derived reasons), and the unmeasured real-artifact latency. `History.jsx` still
renders `matchPercent` with no caveat beside it — now less severe, since the persisted
percentage is the formula's, but the stored `model_caveats` are still never shown there.
