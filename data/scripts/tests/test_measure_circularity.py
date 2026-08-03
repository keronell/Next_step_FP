"""`measure_circularity.py`: the "~94% circular" claim, pinned to the vote log.

Run from repo root with the TRAINING venv (`panel_label_profiles` imports numpy and
pandas; `Scripts/` replaces `bin/` on Windows, as everywhere in
data/scripts/README.md):

    data/venv-training/bin/python -m pytest data/scripts/tests -q

Under the service-test venv it skips whole, like every other pandas-dependent module
here.

## What these are for

"~94% of the time it speaks" travelled this repo as a literal. It is in ADR 0001, in
plan Step 4.1, in `evaluate_matchers.py`'s docstring, and -- the reason it matters --
inside `caveats` in both exported artifacts, from where it reaches
`RecommendationsResponse.model_caveats`, the persisted history and `Results.jsx`.
Nothing computed it. `panel_label_profiles.py` computes the *different* 52.2%
formula-vs-panel number and writes it into `synthetic_agreement_report.md`, which is
easy to mistake for the same measurement; it is not.

So these tests do two things: pin the measurement itself, and pin it *against the
shipped caveat text*, so regenerating the labels breaks the build rather than
silently leaving every artifact asserting a stale rate to users.
"""
import json
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "data" / "scripts"))

pytest.importorskip("numpy")
pytest.importorskip("pandas")

import measure_circularity as mc  # noqa: E402

TRAINING_DIR = REPO_ROOT / "data" / "training"
MODELS_DIR = REPO_ROOT / "data" / "models"

#: The rate the caveat text quotes, and the slack "~" is allowed to cover.
#: One point either side: wide enough that the literal need not be re-rounded on a
#: re-run that moves a handful of votes, narrow enough that it cannot drift into
#: describing a materially different dataset.
QUOTED_RATE = 0.94
QUOTED_TOLERANCE = 0.01


@pytest.fixture(scope="module")
def measurement():
    return mc.measure(mc.load_votes(TRAINING_DIR / "panel_votes.jsonl"))


def test_the_consensus_filter_reproduces_the_recorded_silver_count(measurement):
    """232 is the row count every recorded metric in this deliverable rests on.

    Recomputed from the raw votes rather than read from `silver_labels.parquet`, so
    this also checks that the vote log and the parquet still describe one dataset.
    """
    recorded = json.loads((TRAINING_DIR / "dataset_metadata.json").read_text(encoding="utf-8"))
    assert measurement.silver_profiles == recorded["n_rows"] == 232
    assert measurement.prompt_version == recorded["silver_prompt_versions"][0]


def test_the_quoted_circularity_rate_is_what_the_vote_log_actually_shows(measurement):
    rate = measurement.vote_level.follow_rate
    assert abs(rate - QUOTED_RATE) <= QUOTED_TOLERANCE, (
        f"the vote log gives {rate:.1%}, but ADR 0001, plan Step 4.1 "
        f"and both artifacts' caveats all say ~{QUOTED_RATE:.0%}"
    )


@pytest.mark.parametrize("artifact", ["matcher_logistic_v2.json", "matcher_nn_v1.json"])
def test_the_shipped_artifacts_quote_the_rate_this_script_measures(measurement, artifact):
    """The caveat reaches users, so a stale rate there is a wrong claim to a user.

    The text is parsed rather than string-matched against a hardcoded sentence: the
    wording is `export_model.build_caveats`' to change, the *number* is not.
    """
    path = MODELS_DIR / artifact
    if not path.exists():
        pytest.skip(f"{artifact} not exported in this tree")
    caveats = json.loads(path.read_text(encoding="utf-8"))["caveats"]
    quoted = [
        int(m.group(1)) / 100
        for caveat in caveats
        for m in [re.search(r"answer key derived from careers\.json bonuses ~(\d+)%", caveat)]
        if m
    ]
    assert quoted, f"{artifact} carries no answer-key circularity caveat at all"
    assert abs(quoted[0] - measurement.vote_level.follow_rate) <= QUOTED_TOLERANCE


def test_shortlist_containment_is_structural_and_not_evidence(measurement):
    """Stage 2 cannot leave the answer-key-derived shortlist, so 100% measures nothing.

    Held as a property because it is the one number here a reader could mistake for a
    strong finding about the panel. If it ever drops below 1.0 the prompt's `ids`
    constraint has stopped binding, and `measure_circularity`'s framing of it as
    structural would become false.
    """
    assert measurement.vote_level.shortlist_containment == 1.0


def test_the_two_readings_of_following_the_key_are_materially_different(measurement):
    """The decision document reports both; this pins that doing so is not decorative.

    "Follows the key" under any-bonus and under +3-primary-rules-only are different
    questions, and if they ever coincided the document's disclosure of the weaker
    reading would be padding rather than a disclosure.
    """
    votes = measurement.vote_level
    assert votes.follow_rate - votes.follow_rate_primary > 0.10


def test_the_label_level_rate_agrees_with_the_vote_level_one(measurement):
    """The claim is about votes; the thing that trains a model is the consensus label.

    They are computed over different populations -- the rates are over the 651 votes and
    the 217 labels for which the key speaks -- so agreement is a fact about this dataset
    rather than an identity, which is why the document may quote one rate for both
    without qualifying it.
    """
    assert abs(
        measurement.label_level.follow_rate - measurement.vote_level.follow_rate
    ) <= QUOTED_TOLERANCE
