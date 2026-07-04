# Matching Module Rework — Neural Network Design Walkthrough

A complete walkthrough of how the matching module could be reworked from the current
formula-based RAG blend into a learned/neural-network matcher, given four data sources:

- user answers to the expert questions
- expert answers to the questions (the supervision signal)
- fresh job ads
- additional info the user fills in manually

The key question that determines everything downstream is **what "expert answers"
actually are**, because that is your supervision signal. The pipeline below assumes the
most useful interpretation, then flags the alternatives.

---

## 0. What you have today vs. what changes

Today `backend/app/services/matching_service.py` is a fixed linear blend:

```
final = 0.40·questionnaire_fit + 0.40·semantic_similarity + 0.20·skill_overlap
```

The weights (`FORMULA_WEIGHTS`) and the per-career question weights (`careers.json`
`weights`/`bonuses`) are **hand-authored**. The NN rework replaces *hand-authored weights
with learned ones* — the three signals don't disappear, they become input features to a
model that learns how to combine them from data. That's the honest framing: you're not
throwing away the RAG pipeline, you're learning the blend.

---

## 1. Define the supervision signal (the crux)

"User answers to the expert questions **with expert answers** to the questions" could mean
two very different things:

**Interpretation A — experts gave the *correct field* for each answer profile (true labels).**
An expert looked at a filled questionnaire (+ manual info) and said "this person →
Data Scientist." This is the gold case: you have `(features, correct_career)` pairs.
→ **supervised classification.** This is the primary path built out below.

**Interpretation B — experts answered the questionnaire *as the archetype* of each field.**
i.e. "here's how an ideal Backend Engineer answers q1–q10." That's not labels, it's
*reference vectors*. → you'd use it for **metric learning / similarity**, not
classification (Section 7).

Most likely you want A, possibly seeded by B. Assume A as primary.

A reality check up front: **6 classes, 10 questions, plus free-text.** A neural net is
data-hungry. If experts label only a few hundred profiles, a NN will overfit and lose to
logistic regression / gradient boosting. So the design treats "neural network" as the
target but keeps a **gradient-boosted baseline** as the thing it has to beat. Don't skip
that.

---

## 2. Assemble the training table

One row = one user (or one expert-labeled profile). Columns:

**A. Questionnaire features (structured)**
- `q1…q10` as the raw 0–3 ordinal values. Don't pre-collapse them with the old weights —
  that throws away exactly the signal the NN should learn.
- Encode missing (branched-away `q3`/`q9`) explicitly: either a `q3_present` mask bit
  alongside the value, or NaN→learned embedding. The mask matters because "skipped because
  the branch hid it" carries information.

**B. Manual free-text the user fills (unstructured)**
- "What do you want from a career," current background, projects, etc.
- Embed it with the **same `all-MiniLM-L6-v2` model already loaded** in `main.py` lifespan
  → a 384-dim vector. The embedder is already warm; reuse it, don't add a second model.

**C. The three existing signals as features (don't waste the RAG pipeline)**
- `semantic_similarity` per career (6 numbers) — straight from ChromaDB, the same
  `1 − cosine` computed now.
- `skill_overlap` per career (6 numbers) — from `job_postings_service.skill_counts`.
- Optionally the old `questionnaire_fit` per career as a 6-number prior. Feeding the
  heuristic in as a feature usually *helps* and gives the NN a strong starting baseline to
  refine.

**D. Label**
- `correct_career ∈ {frontend, backend, data-science, devops, product-manager, ux-designer}`
  from the expert.
- If experts give a *ranking* or *top-2*, even better — keep it (Section 6).

So each row ≈ `[10 ordinals + 10 masks] + [384 text dims] + [6 semantic + 6 overlap + 6 fit]`
→ ~422-dim input, one categorical label.

---

## 3. Where "fresh job ads" enter

Job ads are **not training labels** — nobody labels an ad with a user's correct career.
They enter in two legitimate ways:

1. **As the market signal (what you already do):** ads → ChromaDB + skill counts → the
   `semantic_similarity` and `skill_overlap` features above. "Fresh" matters because the
   embeddings/skill-demand drift; you rebuild the Chroma store (`build_rag.py`)
   periodically so those features track the current market. The NN consumes the *derived
   features*, not raw ads.

2. **As a domain-adaptation/pretraining corpus (optional, advanced):** you can fine-tune
   or distill the text encoder on your job-ad corpus so the 384-dim embeddings separate the
   6 fields better than generic MiniLM. Nice-to-have, not v1.

Key point: **the model can stay fixed while job ads change.** Fresh ads update the
*features at inference time* through the existing RAG path. You only retrain the NN when
you get new *labeled* data, which is a much slower cadence. Keep those two refresh loops
separate.

---

## 4. The network itself

For ~400 inputs, 6 classes, modest data — keep it small:

```
Input (≈422-dim, with the 384 text dims optionally projected down to ~64 first)
  → Dense(128) + ReLU + Dropout(0.3) + BatchNorm
  → Dense(64)  + ReLU + Dropout(0.3)
  → Dense(6)   logits
  → softmax
```

- **Loss:** cross-entropy. If experts give soft/partial labels or top-2, use soft-target
  cross-entropy (KL to the expert distribution) — this is strictly better than forcing one
  hot label and matches the UX, which already shows a *ranked top-3*.
- **Output = a probability distribution over the 6 careers.** That's your `matchPercent`
  directly: `round(prob * 100)`, and the top-3 by probability replaces the
  `scored.sort()[:TOP_N]` at the bottom of `match()`. The response shape
  (`id, matchPercent, score, …`) doesn't change — only how `score` is produced.
- **Class imbalance:** experts will label more of some fields. Use class weights or focal
  loss.
- **Regularization is the whole game here** given small data: heavy dropout, weight decay,
  early stopping on a validation split. Stratify the split by career.

Treat two-tower/metric learning (Section 7) as the alternative if data is too small for
this.

---

## 5. Keeping explainability (you'd lose it for free otherwise)

The current `score_breakdown` and `reasons` are a real product feature — a black-box
softmax kills them. Preserve them:

- **Keep the three signals as the breakdown.** Even with a NN, you still computed
  `semantic_similarity`, `skill_overlap`, and the heuristic `fit` as inputs — keep
  surfacing them in `score_breakdown`. They're now *explanatory features* rather than the
  literal formula, but they're honest and already wired into `Results.jsx`.
- **Attribution for the real driver:** run **SHAP** (or integrated gradients) on the model
  per prediction to get "q7 and your text about 'building reliable systems' pushed you
  toward DevOps." Precompute SHAP for the structured features cheaply; this powers a richer
  `reasons` list.
- `matched_skills` / `missing_skills` stay exactly as today — they come from the
  skill-overlap path, independent of the scorer.

---

## 6. Training, validation, and the bar to clear

- **Split:** stratified train/val/test by career. With small data, k-fold CV.
- **Baselines it must beat:** (1) the current linear formula, (2) logistic regression,
  (3) gradient-boosted trees (XGBoost/LightGBM) on the same feature table. **Honestly, on a
  few hundred labeled rows, (3) will likely win and is far easier to ship.** Only adopt the
  NN if it clearly beats GBT on held-out accuracy/top-2 accuracy. Frame the project as
  "learned matcher," and let the data pick the model class.
- **Metrics:** top-1 accuracy is the wrong sole metric for a career recommender. Use
  **top-2 / top-3 accuracy** (the UI shows 3) and a ranking metric (NDCG/MRR) against
  expert rankings. Also calibration (reliability curve) since you display percentages — an
  uncalibrated softmax showing "92%" that's right 60% of the time is a trust problem; apply
  temperature scaling.
- **Expert agreement ceiling:** have ≥2 experts label an overlap set, measure inter-rater
  agreement (Cohen's κ). The model can't meaningfully beat the noise floor of expert
  disagreement; that κ is your real target.

---

## 7. If data is too small for classification (very likely at first)

Use the experts' answers as **reference profiles** and do **metric learning** instead of
classification:

- Build a small **two-tower / embedding** model: encode the user's feature vector into a
  learned space; encode each career's expert-archetype profile into the same space; train
  with a triplet/contrastive loss so users land near their correct career and far from
  others.
- At inference: nearest career(s) by cosine in the learned space → ranked list. This needs
  far less data than a 6-way softmax, degrades gracefully, and naturally produces a
  *ranking* with distances you can show as confidence. New careers can be added by supplying
  one expert archetype — no retrain of a 6-way head. This is the pragmatic "neural" path
  for a cold start, and it sits right on top of the embedding infra you already run.

---

## 8. Serving — fitting it into the existing architecture

- Train **offline** (notebook/script under `data/scripts/`), export the model: ONNX or a
  TorchScript/`.pkl` artifact + a small preprocessing transformer (scaler, the missing-mask
  logic).
- Load it **once in the `main.py` lifespan**, exactly like the embedding model + Chroma
  collection are loaded today. Inference is a sub-millisecond matrix multiply — no latency
  concern.
- `matching_service.match()` keeps its signature (`answers, candidates → list[dict]`).
  Inside, instead of the linear blend you: build the feature vector (reusing
  `candidate.semantic_similarity`, `candidate.market_skills`, and the embedded free-text),
  run the model, take top-3, fill the same dict shape. **The fallback chain is unchanged** —
  if the model artifact is missing or errors, fall back to the current formula. Same
  defensive posture already in place for ChromaDB/Supabase being down. Keep
  `FORMULA_WEIGHTS` as that fallback.
- `careers.json` `weights`/`bonuses` stay as the offline fallback's brain; the NN supersedes
  them when present.

---

## 9. The feedback flywheel (why this gets better over time)

You already persist every submission to `public.submissions` (answers + recommendations)
and now track `selected_career` and `roadmap_progress`. That's latent training data:

- **Weak label:** which career the user *clicked into* (`selected_career`) and made roadmap
  progress on is implicit positive feedback.
- Combine expert gold labels (high-quality, few) with these behavioral weak labels (noisy,
  many) → semi-supervised retraining. Over time the behavioral data can dominate and the
  model adapts to real users, not just expert priors.
- This closes the loop: expert labels bootstrap v1; user behavior trains v2+.

---

## TL;DR of the recommended path

1. Treat expert labels as a **6-way classification** target; verify inter-rater κ first.
2. Feature vector = **raw q1–q10 + masks + free-text embedding (reuse MiniLM) + the existing
   3 RAG signals per career**.
3. Job ads stay in the **feature pipeline** (semantic + skill signals), refreshed on their
   own cadence; they are not labels.
4. **Beat a gradient-boosted baseline before committing to a NN** — at small data scale GBT
   or metric-learning likely wins, and that's fine.
5. Output a **probability distribution → top-3**, keep `score_breakdown` from the 3 signals +
   **SHAP** for `reasons`, calibrate the percentages.
6. Serve from the **lifespan loader**, keep the current formula as the **fallback**, response
   shape unchanged.
7. Use `submissions` + `selected_career` as a **weak-label flywheel** for later versions.

---

## Suggested next steps

- Sketch the concrete `match()` rewrite (feature assembly + model load + fallback).
- A training script skeleton under `data/scripts/`.
- Start with the **GBT baseline** so you have a number to beat before any NN work.
