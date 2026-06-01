# Neural field matcher — design notes (living doc)

Short reference for **adjusting or updating** the idea: map **user questionnaire answers** to **top 3–5 canonical study fields**, optionally informed by **job ads (RAG)** and **synthetic expert annotations**.

**Related:** `WORKFLOW_REDESIGN.md` (full workflow), `data/ADAPTIVE_QUESTIONNAIRE_INSTRUCTIONS.md` (taxonomy + phases), `data/scripts/answer_questions_local.py` (expert CSV), `data/scripts/build_rag.py` + `data/jobs/chroma/` (job index).

---

## 1. Objective

- **Input:** User responses after quiz (same aggregation you use today, e.g. abstract label / skill vector).
- **Output:** Ranked **3–5 fields** from the fixed **16-field taxonomy**, with scores or probabilities.
- **Non-goals (v1):** End-to-end LLM ranking; training only on raw job text with no field supervision.

---

## 2. Three data sources (roles)

| Source | Typical role | Notes |
|--------|----------------|------|
| **Expert / synthetic answers** | **Training targets** (`y`): soft multi-field distribution per (question, persona, target_field) row. | From `question_bank_answered_local.csv` (`field_scores_json`, `predicted_fields`). Filter rows with empty `error`. Synthetic data = bootstrap, not gold. |
| **User answers** | **Inference input** (`X`): same feature construction as training when simulating users. | Align dimensions with `question_bank_labeled.csv` / quiz pipeline. |
| **Job ads (Chroma + raw JSON)** | **Auxiliary signal:** field priors, reranking, or field-level prototypes — **not** the only label. | Market skew (sparse fields) must be handled with weights, balancing, or rerank only. |

**Principle:** Learn a mapping **user feature space → field distribution**. Job text and user text are not comparable without a **trained** bridge; do not rely on untrained cosine similarity alone.

---

## 3. Phased approach (editable checklist)

**Phase A — Contract**  
Define `X` dimension, normalization, missing values; define `y` from `field_scores_json` (renormalize, clipping). Document in one place (this file or `data/reports/ml_feature_spec.md`).

**Phase B — Baseline model**  
Small **MLP** (or similar) on `X` → 16 logits. Loss: **BCE-with-logits** vs soft `y`, or **KL** to soft targets. Prefer **sigmoid + multi-label** if users can match several fields; **softmax** if product insists on a single primary field.

**Phase C — Jobs integration (pick one strategy)**  
- **C1:** Per-field job prototype vectors + late fusion / bias terms.  
- **C2:** Neural top-K + **RAG rerank** using Chroma metadata (`field`, skills, similarity).  
- **C3:** Auxiliary task: predict **field** from job embedding (uses labeled jobs only).

**Phase D — Product**  
Wire inference behind a flag; adaptive quiz uses **entropy / margin** from model outputs; roadmap queries RAG by top fields.

---

## 4. Open decisions (fill in as you iterate)

| Decision | Options | Current leaning |
|----------|---------|-------------------|
| Output type | Multi-label vs single primary + secondary | _TBD_ |
| Training unit | Per-question rows vs aggregated “session” vectors | _TBD_ |
| Job signal in v1 | None / prototype / rerank only | _TBD_ |
| Deployment | CPU ONNX vs Torch in-process | _TBD_ |
| Minimum expert rows before train | e.g. 500 / 2k / field-balanced | _TBD_ |

---

## 5. Risks and mitigations

- **Synthetic bias:** Plan for future real user + self-reported field labels; keep `prompt_version` / `run_id` in training logs.
- **JSON / parse failures:** Block or down-weight bad expert rows; improve retry/parser in annotator (see adaptive instructions Step 4).
- **Imbalanced job counts per field:** Inverse-frequency weights, targeted scrape (`pipeline.py --fields`), or defer job fusion until counts improve.

---

## 6. Artifact map (implement later)

| Piece | Suggested location |
|-------|---------------------|
| Training script + model definition | `data/models/` (e.g. `train_field_matcher.py`) |
| Saved weights | `data/models/checkpoints/` or `.pkl` / `.onnx` |
| Inference wrapper | `backend/matching.py` (or next to `compute_results`) |

---

## 7. Revision log

| Date | Change |
|------|--------|
| 2026-05-23 | Initial stub: sources, phases, open decisions, risks. |

_Update this table whenever you change scope or architecture._
