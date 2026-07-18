"""Learned matcher artifact: load + inference + attribution. No ML runtime needed.

The Gate 2 winner is multinomial logistic regression, so the artifact is plain JSON
(scaler stats + coefficients) written by data/scripts/export_model.py, and inference
is a matrix multiply implemented here with stdlib math. Attribution is exact for a
linear model: contribution(feature, class) = coef[class][feature] * x_scaled[feature],
centered against the across-class mean so shared shifts cancel (softmax-invariant).

Trained on SILVER labels (synthetic LLM panel) — prototype quality; the artifact
carries `label_source` so served responses can be stamped accordingly.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

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
        # consumers actually receive them).
        self.caveats: list[str] = list(artifact.get("caveats", []))

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

    @classmethod
    def load(cls, path: str | Path) -> "MatcherModel":
        p = Path(path)
        if not p.exists():
            raise MatcherModelError(f"model artifact not found: {p}")
        try:
            return cls(json.loads(p.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise MatcherModelError(f"malformed model artifact {p}: {exc}") from exc

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
            b + sum(w * x for w, x in zip(row, z))
            for row, b in zip(self.coef, self.intercept)
        ]
        peak = max(logits)
        exps = [math.exp(v - peak) for v in logits]
        total = sum(exps)
        return {cid: e / total for cid, e in zip(self.careers, exps)}

    def contributions(self, vector: list[float], career_id: str) -> dict[str, float]:
        """Exact per-feature contribution to `career_id`'s logit, centered against
        the mean across classes (positive = pushes toward this career)."""
        z = self._scaled(vector)
        idx = self.careers.index(career_id)
        n_c = len(self.careers)
        out: dict[str, float] = {}
        for j, name in enumerate(self.feature_names):
            own = self.coef[idx][j] * z[j]
            avg = sum(self.coef[c][j] * z[j] for c in range(n_c)) / n_c
            out[name] = own - avg
        return out
