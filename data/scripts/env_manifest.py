"""Environment manifest embedded in every generated training report.

Three separate mechanisms protect the recorded numbers, and they are not
substitutes for one another:

    the lockfile (data/requirements-training.txt)  PREVENTS drift
    dataset_digest() (dataset_guards.py)           DETECTS drift
    this manifest                                  ATTRIBUTES a number to an environment

Without the third, a report is a number with no provenance: when a future run
disagrees with a recorded one, there is nothing to diff. `dataset_digest()` hashes
feature+label *content* via `pd.util.hash_pandas_object`, so a numpy dtype
promotion or a pyarrow parquet-reader change moves it as easily as a pandas change
does — which is why the packages listed here are named individually rather than
summarised as "the training stack".

Stdlib-only on purpose: this module is imported by report generators that must not
gain a dependency, and its tests run under the service-test venv (which has none of
the training stack installed) precisely to prove that.
"""
from __future__ import annotations

import platform
import sys
from importlib.metadata import PackageNotFoundError, version

# Distribution names (as `pip install` spells them), not import names — resolved
# through importlib.metadata so the manifest reports what is actually installed
# rather than what the lockfile intended.
DIGEST_RELEVANT_PACKAGES = (
    # The digest is computed through these three: parquet read + content hash.
    "numpy",
    "pandas",
    "pyarrow",
    # Gate-1/Gate-2 metrics are computed through these.
    "scikit-learn",
    "scipy",
    "joblib",
    "threadpoolctl",
    "lightgbm",
    "torch",
)

NOT_INSTALLED = "not installed"


def package_versions(packages=DIGEST_RELEVANT_PACKAGES) -> dict[str, str]:
    """Resolved version of each distribution, `NOT_INSTALLED` when absent.

    Absent packages are recorded rather than omitted: "torch is not in this
    environment" is a fact about the run, and a manifest with the key missing
    looks complete when it is not."""
    resolved = {}
    for name in packages:
        try:
            resolved[name] = version(name)
        except PackageNotFoundError:
            resolved[name] = NOT_INSTALLED
    return resolved


def environment_manifest() -> dict:
    """Everything needed to decide whether two runs are comparable."""
    return {
        "python": platform.python_version(),
        # The build string, not just X.Y.Z — a rebuilt interpreter at the same
        # version number is a different environment.
        "python_full": " ".join(sys.version.split()),
        "implementation": sys.implementation.name,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "packages": package_versions(),
    }


def manifest_markdown(manifest: dict) -> str:
    """Render a manifest as the `## Environment` section of a report.

    The manifest is a required argument, deliberately: a default that read the live
    environment would be the exact failure this function exists to prevent — a
    report re-rendered later would describe the environment reading it rather than
    the one that produced its numbers."""
    m = manifest
    packages = "\n".join(f"| {name} | {ver} |" for name, ver in sorted(m["packages"].items()))
    return f"""## Environment

Every number in this report is only comparable to runs from an equivalent
environment. `dataset_digest` hashes feature and label *content*, so a change to
any package below can move it — and if it moves, nothing here is comparable to
recorded history (see docs/dev-23-nn-rework-plan.md Step 1).

- Python: {m["python"]} ({m["implementation"]}) — `{m["python_full"]}`
- Platform: {m["platform"]} ({m["machine"]})

| package | version |
|---|---|
{packages}
"""
