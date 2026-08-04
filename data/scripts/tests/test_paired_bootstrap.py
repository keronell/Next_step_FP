"""The paired bootstrap's sampling unit is the PROFILE, not the profile-seed row.

Round 1 (DEV-93) scores every model under 5 experiment seeds, so each of the 232
profiles contributes 5 top-2 hit indicators. Those 1,160 rows are not 1,160
independent observations: the same profile appears in all five. Resampling them as
if they were would understate the standard error by roughly sqrt(5) = 2.2x and
silently narrow every confidence interval in the deliverable — the exact failure
this module exists to prevent, and one that leaves no trace in the output.

The contract, stated as properties a wrong implementation cannot satisfy:

1. Averaging across seeds happens FIRST, inside the sampling unit. So adding
   replicate seeds that carry no new information cannot move the CI at all.
2. Only the per-profile average matters. Permuting which seed contributed which
   value, within a profile, changes nothing.
3. Resampling draws profile ids, so a profile enters a resample with all of its
   seeds or none of them.

Run under the hash-pinned training venv (data/scripts/README.md; `Scripts/` rather
than `bin/` on Windows):

    data/venv-training/Scripts/python -m pytest data/scripts/tests -q

Under the service-test venv this module skips whole, like `test_nn_model.py`.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

np = pytest.importorskip("numpy")
# The bootstrap itself is pure numpy, but it lives in `sweep_variants`, whose
# module-level imports reach `nn_model` and therefore torch. Guarded explicitly so
# this module SKIPS rather than ERRORS under the service-test venv — today it would
# skip on numpy alone, which is an accident of what happens to be installed there
# rather than a property of this file.
pytest.importorskip("sklearn")
pytest.importorskip("torch")

from sweep_variants import paired_bootstrap  # noqa: E402


def make_paired_hits(n_profiles=232, n_seeds=5, seed=0):
    """Per-profile hit indicators for two models that genuinely vary across seeds.

    Variation within a profile is the whole point: if every seed agreed, a
    row-resampling implementation and a profile-resampling one would be much harder
    to tell apart, and the test would pass against the bug.
    """
    rng = np.random.default_rng(seed)
    profile_ids = np.repeat([f"profile-{i:03d}" for i in range(n_profiles)], n_seeds)
    # Per-profile difficulty, so profiles are heterogeneous and the between-profile
    # variance the bootstrap is supposed to capture is real.
    p_a = np.repeat(rng.uniform(0.3, 0.95, n_profiles), n_seeds)
    p_b = np.repeat(rng.uniform(0.3, 0.95, n_profiles), n_seeds)
    hits_a = (rng.random(n_profiles * n_seeds) < p_a).astype(float)
    hits_b = (rng.random(n_profiles * n_seeds) < p_b).astype(float)
    return profile_ids, hits_a, hits_b


def test_replicate_seeds_carry_no_information_and_cannot_narrow_the_ci():
    """Five identical copies of one seed must give exactly the one-seed CI.

    This is the property that fails loudly against the bug. Averaging inside the
    unit makes the per-profile value identical for any number of replicates, so the
    interval cannot move. Resampling profile-seed rows instead would see 5x the
    rows, believe it had 5x the evidence, and shrink the interval by about sqrt(5).
    """
    profile_ids, hits_a, hits_b = make_paired_hits(n_seeds=1)

    one_seed = paired_bootstrap(profile_ids, hits_a, hits_b, random_state=7)
    five_replicates = paired_bootstrap(
        np.repeat(profile_ids, 5), np.repeat(hits_a, 5), np.repeat(hits_b, 5),
        random_state=7,
    )

    assert five_replicates["delta"] == pytest.approx(one_seed["delta"])
    assert five_replicates["ci_low"] == pytest.approx(one_seed["ci_low"])
    assert five_replicates["ci_high"] == pytest.approx(one_seed["ci_high"])
    # The replicated call really did see 5x the rows -- otherwise the equality above
    # would be trivially satisfied by an implementation that ignored the extra data
    # for some other reason, and the test would prove nothing about the sampling unit.
    assert five_replicates["n_profiles"] == one_seed["n_profiles"] == 232
    assert five_replicates["n_rows"] == 232 * 5
    assert one_seed["n_rows"] == 232


def test_only_the_per_profile_average_reaches_the_resample():
    """Permuting which seed contributed which value, within a profile, changes
    nothing — the seed is carried inside the unit, never resampled as if it were an
    independent observation."""
    profile_ids, hits_a, hits_b = make_paired_hits()
    n_seeds = 5

    rng = np.random.default_rng(3)
    shuffled_a, shuffled_b = hits_a.copy(), hits_b.copy()
    for start in range(0, len(profile_ids), n_seeds):
        block = slice(start, start + n_seeds)
        order = rng.permutation(n_seeds)
        shuffled_a[block] = hits_a[block][order]
        shuffled_b[block] = hits_b[block][order]
    assert not np.array_equal(shuffled_a, hits_a)  # the permutation did something

    original = paired_bootstrap(profile_ids, hits_a, hits_b, random_state=11)
    permuted = paired_bootstrap(profile_ids, shuffled_a, shuffled_b, random_state=11)

    assert permuted == original


def test_the_point_estimate_is_the_mean_over_profiles_not_over_rows():
    """With unequal seed counts the two differ, and the profile is the unit.

    An unbalanced pool is not hypothetical: a resumed run that lost a seed, or a
    profile dropped from one seed's folds, produces exactly this shape. Row-meaning
    would silently weight the better-covered profiles more.
    """
    profile_ids = np.array(["p0", "p0", "p0", "p0", "p1"])
    hits_a = np.array([1.0, 1.0, 1.0, 1.0, 0.0])
    hits_b = np.array([0.0, 0.0, 0.0, 0.0, 0.0])

    out = paired_bootstrap(profile_ids, hits_a, hits_b, n_resamples=200, random_state=1)

    # p0 differs by 1.0, p1 by 0.0 -> mean over the two profiles is 0.5.
    # The mean over the five rows would be 0.8.
    assert out["delta"] == pytest.approx(0.5)
    assert out["n_profiles"] == 2
