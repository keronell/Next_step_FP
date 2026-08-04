"""The dispatch seam between the serving code and whatever artifact it loads.

`matching_service` and `main` depend on the `Matcher` protocol below, never on a
concrete implementation, so adding a new model family means adding one class that
satisfies this interface — not rewiring the call sites.

`load_matcher()` is a free function, deliberately: a classmethod that hands back a
sibling class is a surprise, and dispatch does not belong to any one implementation.

`MatcherModelError` is re-exported here so implementations and callers can import
the failure mode from the seam. It stays defined in `matcher_model` to avoid an
import cycle (this module imports the implementations, not the other way round).
Every failure path raises it, because `main.py` catches exactly that type to fall
back to the formula — a different exception would take service startup down instead.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol, runtime_checkable

from app.services.matcher_model import (
    RANKING_ONLY,
    MatcherModel,
    MatcherModelError,
)
from app.services.matcher_nn import NeuralMatcher
from common.logging import get_logger

logger = get_logger(__name__)

__all__ = ["Matcher", "MatcherModelError", "displays_own_percentages", "load_matcher"]


@runtime_checkable
class Matcher(Protocol):
    """What the serving path requires of a scoring artifact.

    `runtime_checkable` makes `isinstance()` available, but it only checks that
    the members EXIST — not their types or signatures. Treat it as a smoke test;
    real conformance is what the behavioural tests assert.
    """

    #: Feature layout the artifact expects, checked against the candidate careers.
    feature_names: list[str]
    #: Artifact identifier, stamped onto every recommendation it scores.
    version: str
    #: Training-data warnings, carried through to the response and persisted history.
    caveats: list[str]
    #: Serving restrictions the artifact declares, or None for unrestricted. Read
    #: through `displays_own_percentages()` rather than directly — the mapping from
    #: a status string to a serving decision belongs in one place.
    deployment: dict | None

    def predict_proba(self, vector: list[float]) -> dict[str, float]:
        """Career id -> probability, summing to 1."""
        ...

    def contributions(self, vector: list[float], career_id: str) -> dict[str, float]:
        """Feature name -> signed contribution to `career_id`'s logit, centered
        across classes and on the same scale as the logits behind predict_proba."""
        ...


def displays_own_percentages(matcher: Matcher) -> bool:
    """May this artifact's own probabilities reach the screen as `matchPercent`?

    False only for a `ranking_only` artifact — ADR 0005's mitigable-ECE branch, where
    the model is trusted to pick the careers but not to put a number beside them.
    `getattr` rather than attribute access because the protocol is structural: a
    third-party matcher predating this member must degrade to "unrestricted", which
    is the pre-existing behaviour, rather than raising mid-request.
    """
    deployment = getattr(matcher, "deployment", None)
    return not (isinstance(deployment, dict) and deployment.get("status") == RANKING_ONLY)


# Artifact `model_type` -> implementation. New families register here; the NN
# adapter (DEV-23 step 5.2) is one more entry, not a change to the call sites.
_IMPLEMENTATIONS: dict[str, type[Matcher]] = {
    "multinomial_logistic_regression": MatcherModel,
    "probability_averaged_mlp_ensemble": NeuralMatcher,
}


def load_matcher(path: str | Path) -> Matcher:
    """Read the artifact at `path`, dispatch on its `model_type`, and return the
    matching implementation. Raises MatcherModelError on anything unusable —
    missing, malformed, unknown family, or built for another feature layout.
    """
    p = Path(path)
    if not p.exists():
        raise MatcherModelError(f"model artifact not found: {p}")
    try:
        artifact = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise MatcherModelError(f"malformed model artifact {p}: {exc}") from exc
    if not isinstance(artifact, dict):
        raise MatcherModelError(f"model artifact {p} is not a JSON object")

    model_type = artifact.get("model_type")
    implementation = _IMPLEMENTATIONS.get(model_type) if isinstance(model_type, str) else None
    if implementation is None:
        raise MatcherModelError(
            f"unsupported model_type {model_type!r} in {p} — known types: "
            f"{', '.join(sorted(_IMPLEMENTATIONS))}"
        )

    try:
        return implementation(artifact)
    except MatcherModelError:
        raise
    except Exception as exc:
        # Deliberately broad. `main.py`'s lifespan catches MatcherModelError and
        # nothing else, so ANY other exception escaping here takes service startup
        # down instead of engaging the formula fallback CLAUDE.md promises — and the
        # artifact is untrusted input, so the set of ways it can go wrong is not
        # knowable from here. This was not hypothetical: a large-integer
        # `temperature` raised OverflowError out of `math.isfinite`, which the old
        # (KeyError, TypeError) tuple did not cover. `parse_temperature` now rejects
        # that at its source; this stays as the guarantee rather than the fix.
        #
        # Logged with a traceback because the cost of the breadth is that a BUG IN
        # OUR OWN CODE also arrives here and would otherwise be reported as a
        # malformed artifact — which is exactly what happened while this was being
        # written, when a missing import surfaced as "malformed model artifact".
        # The fallback is still the right behaviour; being told why is the fix.
        logger.exception("unexpected error loading matcher artifact %s", p)
        raise MatcherModelError(f"malformed model artifact {p}: {exc!r}") from exc
