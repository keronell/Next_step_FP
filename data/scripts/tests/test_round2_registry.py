"""Round 2's candidate set and the specification it hands to export (DEV-95).

Two properties, both of which a plausible edit takes away silently:

- **The Residual Matcher is not a Round-2 candidate.** ADR 0003's pre-registered rule
  disqualified it from being the shipped neural model, and Round 2 selects the model
  that ships. Re-adding it would produce a selection nobody could honour -- and, given
  Round 1's 23-of-25, it would win.
- **The selected Variant's record is a full specification, not a name.** DEV-97 exports
  whatever this ticket selects. `C3_seed_ensemble` means nothing without the twelve
  constructor defaults behind it, and a transcribed copy of those defaults would age
  quietly the first time one of them changed.

Run under the hash-pinned training venv (`data/scripts/README.md`; `Scripts/` rather
than `bin/` on Windows). Skips whole under the service-test venv.
"""
import inspect
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pytest.importorskip("numpy")
pytest.importorskip("sklearn")
pytest.importorskip("torch")

import sweep_round2 as r2  # noqa: E402
from nn_model import NNClassifier  # noqa: E402
from sweep_variants import VARIANTS  # noqa: E402


def test_the_disqualified_residual_matcher_is_not_a_round_2_candidate():
    """The rule executing, pinned as code rather than remembered as a decision."""
    registry = r2.round2_registry()

    assert not any(v.kind == "residual" for v in registry.values())
    assert "C4_residual_matcher" in VARIANTS, (
        "Round 1's registry must still carry it -- its numbers are a recorded "
        "measurement and this ticket does not retract them"
    )


def test_every_other_round_1_variant_still_competes():
    """Round 2 changes the model configurations on offer and nothing else. Dropping a
    Round-1 Variant as well would make the two rounds' selection counts incomparable
    for a reason no report states."""
    registry = r2.round2_registry()
    eligible = {n for n, v in VARIANTS.items() if v.kind != "residual"}

    assert eligible <= set(registry)
    assert len(registry) == len(eligible) + len(r2.REFINEMENTS)


def test_a_refinement_may_not_reuse_a_round_1_variants_name():
    """Two different configurations under one name would make the selection counts
    unreadable across the rounds, and the report prints them in one table."""
    clash = {"V0_control": VARIANTS["A1_84_16_16"]}
    with pytest.raises(SystemExit, match="collide"):
        _run_with_refinements(clash, r2.round2_registry)


def test_no_refinement_repeats_a_round_1_configuration_under_a_new_name():
    """A refinement that is a Round-1 Variant with a fresh label would make the
    Round-2 contest narrower than its registry claims, and the report would print two
    rows for one model. Compared on the pair `(kind, kwargs)`, which is what
    `build_variant` actually consumes -- names and rationales are free text."""
    def identity(v):
        return (v.kind, tuple(sorted((k, tuple(x) if isinstance(x, tuple) else x)
                                     for k, x in v.kwargs.items())))

    seen = {identity(v): n for n, v in VARIANTS.items()}
    for name, refinement in r2.REFINEMENTS.items():
        key = identity(refinement)
        assert key not in seen, f"{name} is {seen[key]} under a new name"
        seen[key] = name


def test_the_refinement_budget_is_the_pre_registered_one():
    """Plan Step 2.7 budgets at most six, fixed in advance precisely so that "keep
    tuning until it wins" is unavailable. There is no round 3."""
    assert len(r2.REFINEMENTS) <= 6


def test_no_refinement_carries_an_internal_hyperparameter_search():
    """The Residual Matcher entered Round 1's contest with a score that was a maximum
    over its four-point alpha grid, evaluated on the ranking metric itself, while
    every other Variant contributed a single configuration's score -- optimism
    `nn_rework.md` reports in full. A refinement with its own grid would inherit it,
    and the Round-2 contest would stop being a comparison of single draws.

    `kind == "residual"` is the only kind `build_variant` resolves a grid for."""
    assert all(v.kind in ("mlp", "ensemble") for v in r2.REFINEMENTS.values())


def test_the_specification_carries_every_constructor_argument():
    """A Variant record is an override dict; the shipped model is that dict plus the
    constructor's defaults. Export needs the second one too, and reading it from
    `inspect.signature` is what keeps this record from describing a model nobody
    trained after a default moves."""
    spec = r2.full_specification(VARIANTS["B3_wd_1e-3"])

    expected = {
        name
        for name, p in inspect.signature(NNClassifier.__init__).parameters.items()
        if p.default is not inspect.Parameter.empty
    }
    assert expected <= set(spec)
    # The Variant's own override wins over the default it overrides.
    assert spec["weight_decay"] == 1e-3
    # random_state has no default by design, so it must be recorded explicitly: a
    # neural configuration without its seed is not one configuration.
    assert "random_state" in spec


def test_an_ensembles_specification_reaches_its_members():
    """`SeedEnsemble` collects member arguments with `**kwargs`, so its own signature
    shows none of them. A specification that stopped at the ensemble would name five
    networks without saying what they are."""
    spec = r2.full_specification(VARIANTS["C3_seed_ensemble"])

    assert spec["class"] == "nn_model.SeedEnsemble"
    assert spec["n_members"] == 5
    assert spec["member"]["hidden_sizes"] == NNClassifier(random_state=0).hidden_sizes


def _run_with_refinements(refinements, fn):
    """Swap REFINEMENTS for the duration of one call.

    A fixture-free monkeypatch: `round2_registry` reads the module global, and the
    collision it refuses is a property of the pair rather than of either side."""
    original = r2.REFINEMENTS
    r2.REFINEMENTS = refinements
    try:
        return fn()
    finally:
        r2.REFINEMENTS = original
