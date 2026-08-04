"""The environment manifest is what lets a recorded number be traced back to the
environment that produced it. The lockfile prevents drift and the dataset digest
detects it; neither of them attributes a number to an environment, which is what
these tests protect.

Run from repo root with the service-test venv (the manifest is stdlib-only, so it
does not need the training stack):

    backend/venv/Scripts/python -m pytest data/scripts/tests -q
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from env_manifest import (  # noqa: E402
    DIGEST_RELEVANT_PACKAGES,
    NOT_INSTALLED,
    environment_manifest,
    manifest_markdown,
    package_versions,
)


def test_manifest_reports_full_python_version_and_platform():
    m = environment_manifest()
    assert m["python"] == ".".join(str(p) for p in sys.version_info[:3])
    # "full Python version" means the build string, not just X.Y.Z — a rebuilt
    # interpreter at the same version is a different environment.
    assert sys.version.split()[0] in m["python_full"]
    assert "\n" not in m["python_full"]  # embedded verbatim in a markdown line
    assert m["implementation"] == sys.implementation.name
    assert m["platform"]


def test_manifest_covers_every_digest_relevant_package():
    packages = environment_manifest()["packages"]
    assert set(packages) == set(DIGEST_RELEVANT_PACKAGES)
    # The three the digest itself is computed through must never be dropped from
    # the list, whatever else changes.
    assert {"numpy", "pandas", "pyarrow"} <= set(DIGEST_RELEVANT_PACKAGES)


def test_absent_packages_are_reported_rather_than_omitted():
    """A missing package is a fact about the environment, so it is recorded.
    Omitting the key would make an incomplete manifest look complete."""
    versions = package_versions(["definitely-not-a-real-package-xyz"])
    assert versions == {"definitely-not-a-real-package-xyz": NOT_INSTALLED}


def test_installed_packages_report_their_real_version():
    versions = package_versions(["pytest"])
    assert versions["pytest"] == pytest.__version__


def test_markdown_renders_every_recorded_fact():
    m = environment_manifest()
    md = manifest_markdown(m)
    assert md.startswith("## Environment")
    assert m["python_full"] in md
    assert m["platform"] in md
    for name, ver in m["packages"].items():
        assert f"| {name} | {ver} |" in md


def test_markdown_snapshots_a_supplied_manifest_not_the_live_one():
    """Reports are generated once and read later; the rendered block must describe
    the manifest handed to it, so a report can never be re-rendered against a
    different environment than the one it recorded."""
    md = manifest_markdown({
        "python": "3.14.0",
        "python_full": "3.14.0 (main, Jan 1 2026)",
        "implementation": "cpython",
        "platform": "Fictional-OS-1.0",
        "machine": "AMD64",
        "packages": {"numpy": "1.2.3"},
    })
    assert "Fictional-OS-1.0" in md
    assert "| numpy | 1.2.3 |" in md
    assert environment_manifest()["platform"] not in md


def test_rendering_without_a_manifest_is_not_possible():
    """No live-environment default: it would silently re-render an old report
    against whichever environment happened to be reading it."""
    with pytest.raises(TypeError):
        manifest_markdown()
