"""Linear learned matcher: inference + attribution. No ML runtime needed.

Satisfies the `Matcher` protocol in `matcher.py`; construct it through
`load_matcher()` rather than directly, so `model_type` dispatch is not bypassed.

The Gate 2 winner is multinomial logistic regression, so the artifact is plain JSON
(scaler stats + coefficients) written by data/scripts/export_model.py, and inference
is a matrix multiply implemented here with stdlib math. Attribution is exact for a
linear model: contribution(feature, class) = coef[class][feature] * x_scaled[feature],
centered against the across-class mean so shared shifts cancel (softmax-invariant).

Trained on SILVER labels (synthetic LLM panel) — prototype quality; the artifact
carries `label_source` so served responses can be stamped accordingly.
"""
from __future__ import annotations

import math

from app.services.feature_builder import FEATURE_VERSION


class MatcherModelError(RuntimeError):
    """Artifact missing, malformed, or incompatible with the current features."""


class MatcherModel:
    def __init__(self, artifact: dict):
        self.feature_names: list[str] = artifact["feature_names"]
        self.careers: list[str] = artifact["careers"]
        self.mean: list[float] = artifact["scaler_mean"]
        self.scale: list[float] = artifact["scaler_scale"]
        self.coef: list[list[float]] = artifact["coef"]          # (n_careers, n_features)
        self.intercept: list[float] = artifact["intercept"]      # (n_careers,)
        self.version: str = artifact.get("model_version", "unknown")
        self.label_source: str = artifact.get("label_source", "unknown")
        # Training-data provenance warnings; surfaced on every response the model
        # scores (the artifact's label_source says "see caveats" — this is where
        # consumers actually receive them). Validated here so a malformed value
        # fails at LOAD time (formula fallback engages) rather than surviving until
        # response serialization rejects it mid-request.
        caveats = artifact.get("caveats", [])
        if not isinstance(caveats, list) or not all(isinstance(c, str) for c in caveats):
            raise MatcherModelError("artifact caveats must be a list of strings")
        self.caveats: list[str] = caveats

        # Calibration temperature fitted at export. Divides the logits, so it
        # sharpens (T<1) or flattens (T>1) the probabilities without ever
        # reordering them. Absent or 1.0 => exactly the untempered model.
        # Validated at LOAD time for the same reason caveats are: a bad value
        # must engage the formula fallback, not produce garbage percentages
        # mid-request. T<=0 would flip or explode the ranking.
        temperature = artifact.get("temperature", 1.0)
        if not isinstance(temperature, (int, float)) or isinstance(temperature, bool):
            raise MatcherModelError("artifact temperature must be a number")
        if not math.isfinite(temperature) or temperature <= 0:
            raise MatcherModelError(
                f"artifact temperature must be finite and > 0, got {temperature!r}"
            )
        self.temperature: float = float(temperature)

        n_f, n_c = len(self.feature_names), len(self.careers)
        if artifact.get("feature_version") != FEATURE_VERSION:
            raise MatcherModelError(
                f"artifact feature_version {artifact.get('feature_version')!r} != "
                f"code {FEATURE_VERSION!r} — retrain/re-export required"
            )
        if len(self.mean) != n_f or len(self.scale) != n_f:
            raise MatcherModelError("scaler shape mismatch")
        if len(self.coef) != n_c or any(len(row) != n_f for row in self.coef):
            raise MatcherModelError("coefficient shape mismatch")
        if len(self.intercept) != n_c:
            raise MatcherModelError("intercept shape mismatch")

    # ---------------------------------------------------------------- inference
    def _scaled(self, vector: list[float]) -> list[float]:
        if len(vector) != len(self.feature_names):
            raise MatcherModelError(
                f"feature vector length {len(vector)} != expected {len(self.feature_names)}"
            )
        return [
            (x - m) / s if s else 0.0
            for x, m, s in zip(vector, self.mean, self.scale)
        ]

    def predict_proba(self, vector: list[float]) -> dict[str, float]:
        z = self._scaled(vector)
        logits = [
            (b + sum(w * x for w, x in zip(row, z))) / self.temperature
            for row, b in zip(self.coef, self.intercept)
        ]
        peak = max(logits)
        exps = [math.exp(v - peak) for v in logits]
        total = sum(exps)
        return {cid: e / total for cid, e in zip(self.careers, exps)}

    def contributions(self, vector: list[float], career_id: str) -> dict[str, float]:
        """Exact per-feature contribution to `career_id`'s logit, centered against
        the mean across classes (positive = pushes toward this career).

        Tempered on the same scale as predict_proba, so the contributions keep
        summing to the logit that actually produced the served probability. T is a
        positive scalar, so it never reorders reasons — reason_builder ranks these.
        """
        z = self._scaled(vector)
        idx = self.careers.index(career_id)
        n_c = len(self.careers)
        out: dict[str, float] = {}
        for j, name in enumerate(self.feature_names):
            own = self.coef[idx][j] * z[j]
            avg = sum(self.coef[c][j] * z[j] for c in range(n_c)) / n_c
            out[name] = (own - avg) / self.temperature
        return out
