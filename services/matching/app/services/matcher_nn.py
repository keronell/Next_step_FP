"""Neural learned matcher: numpy inference + integrated-gradients attribution.

Satisfies the `Matcher` protocol in `matcher.py`; construct it through
`load_matcher()` rather than directly, so `model_type` dispatch is not bypassed.

The shipped configuration (DEV-95, `selected_specification` in
`data/training/round2_results.json`) is `SeedEnsemble(n_members=5, dropout=0.5,
weight_decay=1e-2)` — five ReLU MLPs differing only in seed, averaged **in
probability**. Layer widths, depth and member count are all read from the artifact;
nothing here knows that the trained trunk happens to be 84 -> 64 -> 32 -> 16.

numpy, never torch. torch is heavyweight and slow to import and has no business in
a request path; numpy is neither. (It is a declared dependency of this service —
`services/matching/requirements.txt` — but until this module existed nothing under
`services/` imported it, so the plan's claim that it was "already loaded
in-process" was wrong on its second half. See the DEV-94 reproduction record.)

Trained on SILVER labels (synthetic LLM panel) — prototype quality; the artifact
carries `label_source` and `caveats` and both are surfaced per recommendation.

## What the attributions explain, and why it is this and not the other one

Integrated gradients is linear in the model function, so IG over a
probability-averaged ensemble could be computed as the average of the members' own
attributions — but that explains the **mean of the members' logits**, and
`mean(softmax(z_i))` is not `softmax(mean(z_i))`. The mean logit is the logit of a
model nobody serves.

So this module explains the **logit of the mean probability**:

    g_c(x) = log( mean_i softmax(z_i(x))_c ) / T

Three reasons, in the order they decided it:

1. `softmax(g) == predict_proba` exactly, by construction. It is the logit *of the
   served distribution*, so a reason gated on `g` is a reason about the number the
   user sees.
2. It is where the temperature was fitted. `train_models.apply_temperature` is
   `softmax(log(clip(probs)) / t)` — it consumes **probabilities**, and for this
   model those are the averaged ones. Explaining the mean logit would apply T at a
   place no offline fit ever put it. **DEV-97's exporter must fit `temperature` on
   ensemble-averaged OOF probabilities, and revalidate Gate 1 on
   `SeedEnsemble.predict_proba` — the mean of the members' probabilities.** Any
   other choice revalidates a different quantity than the one explained here.
3. `log P` is a logit only up to an additive constant; centering across classes
   pins it. So the centered quantity this module reports is canonical, whereas a
   centered mean-of-logits is the centered logit of nothing in particular.

The price is that attribution is no longer a per-member average: the gradient of
`log P_c` couples the members through `1 / P_c`. `_ensemble_gradient` pays it.

## Completeness is measured, not assumed

For a ReLU network the IG *theorem* is exact — `g` is piecewise-smooth along the
straight path — but a fixed-step **Riemann sum** is not, because the gradient jumps
at activation breakpoints. So the step count adapts: start at `IG_MIN_STEPS`,
double until the relative completeness residual falls under `IG_REL_TOLERANCE`, and
give up at `IG_MAX_STEPS`. `explain()` reports the achieved residual and the step
count it took. A career whose residual never comes under tolerance yields **no
attributions at all** — `contributions()` returns `{}`, `reason_builder` finds
nothing above its threshold and falls through to its non-model wording. Silence
beats numbers that do not add up to what they claim to explain.

Analytic breakpoint tracking would be exact, and is rejected: it means enumerating
activation-pattern changes through the whole trunk.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from app.services.feature_builder import FEATURE_VERSION
from app.services.matcher_model import (
    MatcherModelError,
    parse_deployment,
    parse_temperature,
)
from common.logging import get_logger

logger = get_logger(__name__)

#: Integrated-gradients step schedule. 32 is the plan's starting budget; the cap
#: bounds the worst case at 16x that before the career goes silent.
IG_MIN_STEPS = 32
IG_MAX_STEPS = 512
#: Relative completeness residual a career's attributions must reach to be used.
IG_REL_TOLERANCE = 1e-3
#: Floor on the relative-residual denominator, so a career whose centered logit does
#: not move at all is not judged against a zero divisor. Small enough that it never
#: relaxes the tolerance for a career with anything to explain.
IG_DELTA_FLOOR = 1e-12
#: Mirrors train_models.apply_temperature, so the served probabilities are the same
#: function of the member outputs that offline calibration was fitted against.
PROBABILITY_FLOOR = 1e-9


def _as_array(value, what: str) -> np.ndarray:
    """`np.asarray` with the failure translated into the one exception the serving
    path is allowed to raise. Ragged and non-numeric input raise ValueError, which
    `load_matcher` does not catch."""
    try:
        return np.asarray(value, dtype=np.float64)
    except (ValueError, TypeError) as exc:
        raise MatcherModelError(f"{what} is not a numeric array: {exc}") from exc


@dataclass(frozen=True)
class Attribution:
    """One career's attributions plus the evidence they are trustworthy.

    `contributions()` returns only the mapping; this is what tests and the
    reproduction record read to report how often `m` had to double and what
    residuals were actually achieved.
    """

    contributions: dict[str, float]
    steps: int
    #: |sum(contributions) - centered delta| / |centered delta|. The strict reading
    #: of "relative completeness residual", and the one `converged` gates on.
    residual: float
    #: |sum(contributions) - centered delta|, unnormalized.
    absolute_residual: float
    #: sum(|contribution|). Carried so the alternative denominator — the residual
    #: as a fraction of the explanation's own mass — is derivable without recomputing
    #: anything. Which denominator the tolerance should use is an open question this
    #: ticket measured but could not settle; see the DEV-94 reproduction record.
    attribution_mass: float
    converged: bool


class NeuralMatcher:
    def __init__(self, artifact: dict):
        self.feature_names: list[str] = artifact["feature_names"]
        self.careers: list[str] = artifact["careers"]
        self.version: str = artifact.get("model_version", "unknown")
        self.label_source: str = artifact.get("label_source", "unknown")

        caveats = artifact.get("caveats", [])
        if not isinstance(caveats, list) or not all(isinstance(c, str) for c in caveats):
            raise MatcherModelError("artifact caveats must be a list of strings")
        self.caveats: list[str] = caveats

        # Same load-time validation as the linear path, and for the same reason: a
        # bad value must engage the formula fallback rather than produce garbage
        # percentages mid-request.
        self.temperature: float = parse_temperature(artifact)
        #: Serving restrictions declared by the artifact; None = unrestricted.
        # matcher_nn_v1 declares "ranking_only" -- ADR 0005's mitigable-ECE branch.
        self.deployment: dict | None = parse_deployment(artifact)

        if artifact.get("feature_version") != FEATURE_VERSION:
            raise MatcherModelError(
                f"artifact feature_version {artifact.get('feature_version')!r} != "
                f"code {FEATURE_VERSION!r} — retrain/re-export required"
            )

        activation = artifact.get("activation", "relu")
        if activation != "relu":
            raise MatcherModelError(
                f"unsupported activation {activation!r} — this implementation is ReLU only"
            )

        n_f, n_c = len(self.feature_names), len(self.careers)
        # np.asarray raises ValueError on ragged or non-numeric input, which
        # load_matcher does NOT catch — every failure path here has to reach the
        # lifespan as MatcherModelError or a bad artifact takes startup down instead
        # of falling back to the formula.
        self.mean = _as_array(artifact["scaler_mean"], "scaler_mean")
        self.scale = _as_array(artifact["scaler_scale"], "scaler_scale")
        if self.mean.shape != (n_f,) or self.scale.shape != (n_f,):
            raise MatcherModelError("scaler shape mismatch")
        # A zero scale means a feature was constant in training; the linear path
        # maps it to 0.0 rather than dividing, and so does this one.
        self._safe_scale = np.where(self.scale == 0.0, 1.0, self.scale)
        self._live = self.scale != 0.0

        members = artifact["members"]
        if not isinstance(members, list) or not members:
            raise MatcherModelError("artifact must carry at least one ensemble member")
        self.members: list[list[tuple[np.ndarray, np.ndarray]]] = [
            self._read_member(m, n_f, n_c, i) for i, m in enumerate(members)
        ]

    @staticmethod
    def _read_member(member: dict, n_f: int, n_c: int, index: int):
        """Layer shapes come from the artifact; only the chaining is enforced."""
        try:
            layers = member["layers"]
        except TypeError as exc:  # not a mapping at all
            raise MatcherModelError(f"member {index} is not an object: {exc}") from exc
        if not isinstance(layers, list) or not layers:
            raise MatcherModelError(f"member {index} has no layers")

        read: list[tuple[np.ndarray, np.ndarray]] = []
        expected_in = n_f
        for depth, layer in enumerate(layers):
            try:
                raw_weight, raw_bias = layer["weight"], layer["bias"]
            except (KeyError, TypeError) as exc:
                raise MatcherModelError(
                    f"member {index} layer {depth} is malformed: {exc}"
                ) from exc
            weight = _as_array(raw_weight, f"member {index} layer {depth} weight")
            bias = _as_array(raw_bias, f"member {index} layer {depth} bias")
            if weight.ndim != 2 or bias.ndim != 1:
                raise MatcherModelError(
                    f"member {index} layer {depth}: weight must be 2-D and bias 1-D"
                )
            n_out, n_in = weight.shape
            if n_in != expected_in:
                raise MatcherModelError(
                    f"member {index} layer {depth} expects {n_in} inputs but the "
                    f"preceding layer emits {expected_in}"
                )
            if bias.shape != (n_out,):
                raise MatcherModelError(
                    f"member {index} layer {depth}: bias width {bias.shape[0]} != "
                    f"weight rows {n_out}"
                )
            read.append((weight, bias))
            expected_in = n_out

        if expected_in != n_c:
            raise MatcherModelError(
                f"member {index} emits {expected_in} outputs but the artifact "
                f"declares {n_c} careers"
            )
        return read

    # ---------------------------------------------------------------- inference
    def _scaled(self, vector: list[float]) -> np.ndarray:
        if len(vector) != len(self.feature_names):
            raise MatcherModelError(
                f"feature vector length {len(vector)} != expected {len(self.feature_names)}"
            )
        x = np.asarray(vector, dtype=np.float64)
        return np.where(self._live, (x - self.mean) / self._safe_scale, 0.0)

    def _member_forward(self, member, Z: np.ndarray):
        """Batched forward pass. Returns the logits and each ReLU's activation mask,
        which the backward pass needs and which are only cheap to keep here."""
        h = Z
        masks: list[np.ndarray] = []
        for depth, (weight, bias) in enumerate(member):
            h = h @ weight.T + bias
            if depth < len(member) - 1:
                mask = h > 0.0
                masks.append(mask)
                h = h * mask
        return h, masks

    @staticmethod
    def _softmax(logits: np.ndarray) -> np.ndarray:
        shifted = logits - logits.max(axis=-1, keepdims=True)
        exps = np.exp(shifted)
        return exps / exps.sum(axis=-1, keepdims=True)

    def _mean_probability(self, Z: np.ndarray) -> np.ndarray:
        """The served quantity before temperature: mean over members of each
        member's softmax. Shape (n_rows, n_careers)."""
        per_member = [self._softmax(self._member_forward(m, Z)[0]) for m in self.members]
        return np.mean(per_member, axis=0)

    def _served_probability(self, Z: np.ndarray) -> np.ndarray:
        """Temperature applied exactly as train_models.apply_temperature applies it:
        divide the log of the (clipped) probabilities and renormalize.

        Spelled as the softmax of the explained logit rather than as its own
        expression, because "the softmax of what we explain is what we serve" is the
        whole attribution decision and it should be true by construction, not by two
        expressions agreeing.
        """
        return self._softmax(self._explained_logit(Z))

    def predict_proba(self, vector: list[float]) -> dict[str, float]:
        probs = self._served_probability(self._scaled(vector)[None, :])[0]
        return {cid: float(p) for cid, p in zip(self.careers, probs)}

    # -------------------------------------------------------------- attribution
    def _explained_logit(self, Z: np.ndarray) -> np.ndarray:
        """g(Z) = log(mean member probability) / T. Its softmax is `predict_proba`,
        which is what makes it the logit OF THE SERVED DISTRIBUTION rather than of
        the notional model whose logits are the members' average."""
        clipped = np.clip(self._mean_probability(Z), PROBABILITY_FLOOR, 1.0)
        return np.log(clipped) / self.temperature

    def _ensemble_gradient(self, Z: np.ndarray) -> np.ndarray:
        """d g_c / d Z for every class at every path point. Shape (rows, C, dims).

        The chain rule through the ensemble mean is where explaining the served
        quantity costs more than averaging the members' attributions would:

            d/dZ log(P_c)/T = (1 / (T * P_c)) * (1/M) * sum_i d p_i,c / dZ

        so the members are coupled through the shared 1/P_c and cannot be
        attributed independently. Each member's term is the softmax Jacobian
        p_i,c * (e_c - p_i) pushed back through that member's layers.
        """
        n_rows = Z.shape[0]
        n_c = len(self.careers)
        eye = np.eye(n_c)

        mean_prob = np.zeros((n_rows, n_c))
        summed = np.zeros((n_rows, n_c, Z.shape[1]))
        for member in self.members:
            logits, masks = self._member_forward(member, Z)
            p = self._softmax(logits)
            mean_prob += p
            # V[row, c, k] = d p_c / d logit_k, batched over the class being explained.
            grad = p[:, :, None] * (eye[None, :, :] - p[:, None, :])
            for depth in reversed(range(len(member))):
                grad = grad @ member[depth][0]
                if depth > 0:
                    grad = grad * masks[depth - 1][:, None, :]
            summed += grad
        mean_prob /= len(self.members)

        # Where the probability floor binds, the served logit is a constant and its
        # true derivative is zero. Honouring that keeps completeness meaningful
        # instead of quietly attributing a clipped constant.
        clipped = mean_prob < PROBABILITY_FLOOR
        denom = self.temperature * len(self.members) * np.where(clipped, 1.0, mean_prob)
        gradient = summed / denom[:, :, None]
        gradient[clipped] = 0.0
        return gradient

    def _centered_ig(self, z: np.ndarray, steps: int) -> np.ndarray:
        """Integrated gradients from the baseline (z = 0, the scaler mean) to `z`,
        centered across classes. Shape (C, dims).

        A midpoint Riemann sum: for a piecewise-linear path integrand it is exact on
        every sub-interval that contains no activation breakpoint, which is why
        doubling the step count converges rather than merely wobbling.
        """
        alphas = (np.arange(steps) + 0.5) / steps
        gradient = self._ensemble_gradient(alphas[:, None] * z[None, :])
        attributions = z[None, :] * gradient.mean(axis=0)
        return attributions - attributions.mean(axis=0, keepdims=True)

    def _centered_delta(self, z: np.ndarray) -> np.ndarray:
        """What the attributions must sum to: the change in the centered explained
        logit between the baseline and `z`. Shape (C,)."""
        endpoints = self._explained_logit(np.stack([np.zeros_like(z), z]))
        centered = endpoints - endpoints.mean(axis=1, keepdims=True)
        return centered[1] - centered[0]

    @staticmethod
    def _residuals(attributions: np.ndarray, delta: float) -> tuple[float, float]:
        """Completeness error, absolute and as a fraction of what is explained.

        The strict reading, deliberately. The lenient alternative — dividing by the
        attribution mass `sum(|a_j|)` — is far easier to satisfy, because at 84
        features the mass is an order of magnitude larger than the delta it sums to,
        so a residual that is 3e-3 of what it claims to explain reads as under 1e-3
        of the numbers on the page. That is a thumb on the scale, so this is not it.
        `Attribution.attribution_mass` carries the mass instead, and the reproduction
        record reports both.
        """
        absolute = abs(float(attributions.sum()) - delta)
        return absolute, absolute / max(abs(delta), IG_DELTA_FLOOR)

    def explain(self, vector: list[float], career_id: str) -> Attribution:
        """Attributions for one career, with the evidence they are complete.

        Always returns what it measured, converged or not — `contributions()` is
        where a non-converged result is withheld from serving.
        """
        try:
            idx = self.careers.index(career_id)
        except ValueError as exc:
            raise MatcherModelError(f"unknown career {career_id!r}") from exc

        z = self._scaled(vector)
        delta = float(self._centered_delta(z)[idx])

        steps = IG_MIN_STEPS
        while True:
            attributions = self._centered_ig(z, steps)[idx]
            absolute, residual = self._residuals(attributions, delta)
            if residual < IG_REL_TOLERANCE or steps >= IG_MAX_STEPS:
                break
            steps *= 2

        return Attribution(
            contributions={
                name: float(v) for name, v in zip(self.feature_names, attributions)
            },
            steps=steps,
            residual=residual,
            absolute_residual=absolute,
            attribution_mass=float(np.abs(attributions).sum()),
            converged=residual < IG_REL_TOLERANCE,
        )

    def contributions(self, vector: list[float], career_id: str) -> dict[str, float]:
        """Per-feature contribution to `career_id`'s centered served logit.

        Empty when completeness could not be established: `reason_builder` then
        finds nothing above its threshold and falls through to the non-model
        wording, which is the intended behaviour and not a degraded one.
        """
        result = self.explain(vector, career_id)
        if not result.converged:
            logger.warning(
                "Integrated-gradients completeness residual %.3g for career '%s' "
                "exceeds %g at m=%d — serving no model-derived reasons for it",
                result.residual, career_id, IG_REL_TOLERANCE, result.steps,
            )
            return {}
        # The achieved residual is recorded on the serving path too, not only on the
        # failure branch: "a measured guarantee per request" is only a guarantee if
        # the measurement leaves the process.
        logger.debug(
            "Integrated gradients for career '%s': residual %.3g (absolute %.3g of "
            "mass %.3g) at m=%d",
            career_id, result.residual, result.absolute_residual,
            result.attribution_mass, result.steps,
        )
        return result.contributions
