"""
NextStep data pipeline — scrape → extract skills → build RAG.

Modes
─────
  (default)  Full rebuild: scrape all sources, extract skills, wipe and rebuild RAG.
  --update   Incremental: fetch new ads (merged into existing), skip already-extracted
             skills, upsert new jobs into existing RAG without wiping it.

Usage
─────
    python data/scripts/pipeline.py
    python data/scripts/pipeline.py --update
    python data/scripts/pipeline.py --sources remoteok jobicy themuse
    python data/scripts/pipeline.py --fields "AI Engineering" "Software Architecture"
    python data/scripts/pipeline.py --use-llm
    python data/scripts/pipeline.py --skip-scrape   # rebuild RAG from existing raw files
    python data/scripts/pipeline.py --skip-rag      # stop after extract_skills
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
PYTHON = sys.executable


def run_step(label: str, cmd: list[str]) -> int:
    print(f"\n{'─' * 60}")
    print(f"  STEP : {label}")
    print(f"  CMD  : {' '.join(cmd)}")
    print(f"{'─' * 60}\n")
    t0 = time.time()
    rc = subprocess.run(cmd).returncode
    elapsed = time.time() - t0
    status = "OK" if rc == 0 else f"FAILED (exit {rc})"
    print(f"\n  ── {label}: {status}  ({elapsed:.0f}s) ──")
    return rc


def main():
    parser = argparse.ArgumentParser(
        description="Run the full NextStep data pipeline: scrape → extract skills → build RAG",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Incremental update: merge new job ads into existing files, skip already-"
             "extracted skills, upsert into existing RAG (no wipe).",
    )
    parser.add_argument(
        "--sources",
        nargs="+",
        metavar="SOURCE",
        help="Job sources to scrape. Choices: remoteok jobicy remotive arbeitnow "
             "workingnomads weworkremotely jobspy themuse  (default: all)",
    )
    parser.add_argument(
        "--fields",
        nargs="+",
        metavar="FIELD",
        help="Only scrape/process these canonical fields, e.g. 'AI Engineering'. "
             "Useful for targeted top-up runs on underrepresented fields.",
    )
    parser.add_argument(
        "--max-per-field",
        type=int,
        default=300,
        metavar="N",
        help="Max jobs per canonical field per source in the scraper (default: 300).",
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Enrich skill extraction with Ollama LLM (slow; requires Ollama running).",
    )
    parser.add_argument(
        "--skip-scrape",
        action="store_true",
        help="Skip scraping — re-use existing raw JSON files as-is.",
    )
    parser.add_argument(
        "--skip-rag",
        action="store_true",
        help="Stop after extract_skills; do not build the ChromaDB store.",
    )
    args = parser.parse_args()

    mode = "update" if args.update else "full rebuild"
    print(f"\n{'=' * 60}")
    print(f"  NextStep pipeline  [{mode}]")
    print(f"{'=' * 60}")

    failed: list[str] = []

    # ── Step 1: Scrape ──────────────────────────────────────────────────────
    if not args.skip_scrape:
        cmd = [PYTHON, str(SCRIPTS_DIR / "scrape_job_ads.py")]
        if args.sources:
            cmd += ["--sources"] + args.sources
        if args.fields:
            cmd += ["--fields"] + args.fields
        cmd += ["--max-per-field", str(args.max_per_field)]

        if run_step("Scrape job ads", cmd) != 0:
            failed.append("scrape")
    else:
        print("\n  [skip] Scraping step skipped — using existing raw files.")

    # ── Step 2: Extract skills ──────────────────────────────────────────────
    # extract_skills already skips jobs that have a 'skills' key, so --update
    # behaviour is automatic; no extra flag needed.
    cmd = [PYTHON, str(SCRIPTS_DIR / "extract_skills.py")]
    if args.sources:
        cmd += ["--sources"] + args.sources
    if args.use_llm:
        cmd.append("--use-llm")

    if run_step("Extract skills", cmd) != 0:
        failed.append("extract_skills")

    # ── Step 3: Build RAG ───────────────────────────────────────────────────
    if not args.skip_rag:
        cmd = [PYTHON, str(SCRIPTS_DIR / "build_rag.py")]
        if args.sources:
            cmd += ["--sources"] + args.sources
        if not args.update:
            cmd.append("--reset")   # full rebuild wipes the collection first

        if run_step("Build RAG (ChromaDB)", cmd) != 0:
            failed.append("build_rag")
    else:
        print("\n  [skip] RAG build step skipped.")

    # ── Summary ─────────────────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    if failed:
        print(f"  Pipeline finished with errors in: {', '.join(failed)}")
        print("  Check the output above for details.")
        sys.exit(1)
    else:
        print(f"  Pipeline complete  [{mode}]")
        print("  Verify: python data/scripts/build_rag.py --stats-only")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
