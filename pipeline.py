"""
pipeline.py — Content AI Pipeline for SaveKu (CLI entry point)

Usage:
  python pipeline.py                        Run full pipeline for all accounts
  python pipeline.py --dry-run              Match only, no script generation
  python pipeline.py --account account_01   Run for a single account
  python pipeline.py --output results.json  Custom output filename
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from matcher import run_matching
from generator import generate_script, find_style_ref

load_dotenv()

# ─── Config ───────────────────────────────────────────────────────────────────

API_KEY = ""  # auth handled by claude login (Claude Code CLI)

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"


# ─── Input loading ────────────────────────────────────────────────────────────

def load_inputs() -> tuple:
    """Load all pipeline input files. Exits with a clear message if any are missing."""
    required = {
        "accounts": BASE_DIR / "accounts.json",
        "trends": BASE_DIR / "trends.json",
        "templates": BASE_DIR / "templates.json",
        "style_refs": BASE_DIR / "style_references.json",
        "client_brief": BASE_DIR / "client_brief.md",
    }

    for name, path in required.items():
        if not path.exists():
            sys.exit(f"[ERROR] Missing required file: {path.name}")

    with open(required["accounts"], encoding="utf-8") as f:
        accounts = json.load(f)
    with open(required["trends"], encoding="utf-8") as f:
        trends = json.load(f)
    with open(required["templates"], encoding="utf-8") as f:
        templates = json.load(f)
    with open(required["style_refs"], encoding="utf-8") as f:
        style_refs = json.load(f)
    with open(required["client_brief"], encoding="utf-8") as f:
        client_brief = f.read()

    return accounts, trends, templates, style_refs, client_brief


# ─── Output assembly ──────────────────────────────────────────────────────────

def build_output_entry(match: dict, script: dict | None) -> dict:
    """Assemble a single output entry conforming to output_schema.json."""
    # Extract quality_score embedded by generator.py (not part of script schema)
    quality_score = None
    if script is not None:
        quality_score = script.pop("quality_score", None)

    return {
        "account_id": match["account_id"],
        "trend_id": match.get("trend_id"),
        "template_id": match.get("template_id"),
        "reasoning": match.get("reasoning", {}),
        "fit_score": match.get("fit_score", 0.0),
        "script": script,
        "quality_score": quality_score,
        "no_match_reason": match.get("no_match_reason"),
    }


def build_no_match_entry(match: dict) -> dict:
    """Assemble an output entry for an account with no suitable trend."""
    return {
        "account_id": match["account_id"],
        "trend_id": None,
        "template_id": None,
        "reasoning": match.get("reasoning", {}),
        "fit_score": match.get("fit_score", 0.0),
        "script": None,
        "no_match_reason": match.get("no_match_reason", "No suitable trend found."),
    }


# ─── Lookup helpers ───────────────────────────────────────────────────────────

def get_by_id(items: list, item_id: str) -> dict | None:
    return next((i for i in items if i.get("id") == item_id), None)


# ─── CLI output helpers ───────────────────────────────────────────────────────

def print_match_summary(matches: list, accounts: list, trends: list, templates: list):
    print("\n" + "=" * 60)
    print("MATCHING RESULTS")
    print("=" * 60)
    for m in matches:
        account = get_by_id(accounts, m["account_id"])
        handle = account["handle"] if account else m["account_id"]

        if m.get("trend_id") is None:
            print(f"\n  {handle}")
            print(f"    Trend:    NO MATCH")
            print(f"    Reason:   {m.get('no_match_reason', 'N/A')}")
            print(f"    Score:    {m.get('fit_score', 0.0):.2f}")
        else:
            trend = get_by_id(trends, m["trend_id"])
            template = get_by_id(templates, m["template_id"])
            trend_topic = trend["topic"] if trend else m["trend_id"]
            template_name = template["name"] if template else m["template_id"]

            print(f"\n  {handle}")
            print(f"    Trend:    {trend_topic}")
            print(f"    Template: {template_name}")
            print(f"    Score:    {m.get('fit_score', 0.0):.2f}")
            rationale = m.get("reasoning", {}).get("trend_match_rationale", "")
            if rationale:
                # Word-wrap at 70 chars for readability
                words = rationale.split()
                line = "    Why:      "
                for word in words:
                    if len(line) + len(word) + 1 > 74:
                        print(line)
                        line = "              " + word + " "
                    else:
                        line += word + " "
                if line.strip():
                    print(line)
    print()


def print_final_summary(results: list, output_path: Path):
    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)
    scripted = [r for r in results if r["script"] is not None]
    skipped = [r for r in results if r["script"] is None]

    print(f"  Scripts generated: {len(scripted)}/{len(results)}")
    for r in scripted:
        duration = r["script"].get("total_duration_seconds", "?")
        qs = r.get("quality_score")
        if qs:
            overall = qs.get("overall_score", "?")
            approved = qs.get("auto_approved", False)
            flag = "✓" if approved else "!"
            score_str = f"  quality: {overall}/10 [{flag}]"
        else:
            score_str = ""
        print(f"    {r['account_id']:12s}  {duration}s  (trend: {r['trend_id']}, template: {r['template_id']}){score_str}")

    if skipped:
        print(f"\n  No-match accounts ({len(skipped)}):")
        for r in skipped:
            print(f"    {r['account_id']:12s}  {r['no_match_reason']}")

    print(f"\n  Output saved to: {output_path}")
    print()


# ─── Pipeline orchestration ───────────────────────────────────────────────────

def run_pipeline(args):
    # ── API key check ──
    # ── Load inputs ──
    print("Loading input files...")
    accounts, trends, templates, style_refs, client_brief = load_inputs()
    print(f"  {len(accounts)} accounts, {len(trends)} trends, {len(templates)} templates loaded.")

    # ── Filter to single account if requested ──
    if args.account:
        filtered = [a for a in accounts if a["id"] == args.account]
        if not filtered:
            sys.exit(f"[ERROR] Account '{args.account}' not found in accounts.json")
        accounts = filtered
        print(f"  Filtered to single account: {accounts[0]['handle']}")

    # ── Stage 1 & 2: Matching ──
    print("\nRunning context matching + template selection...")
    matches = run_matching(accounts, trends, templates, API_KEY)

    # Filter matches to only requested accounts
    requested_ids = {a["id"] for a in accounts}
    matches = [m for m in matches if m["account_id"] in requested_ids]

    print_match_summary(matches, accounts, trends, templates)

    if args.dry_run:
        print("Dry run complete. No scripts generated.")
        return

    # ── Stage 3: Script generation ──
    print("Generating scripts...\n")
    OUTPUT_DIR.mkdir(exist_ok=True)
    results = []

    for match in matches:
        account = get_by_id(accounts, match["account_id"])
        handle = account["handle"]

        if match.get("trend_id") is None:
            print(f"  {handle}: skipping — {match.get('no_match_reason', 'no trend match')}")
            results.append(build_no_match_entry(match))
            continue

        trend = get_by_id(trends, match["trend_id"])
        template = get_by_id(templates, match["template_id"])
        style_ref = find_style_ref(style_refs, trend.get("niche_tags", []))

        print(f"  {handle} → '{trend['topic']}' via {template['name']}")
        try:
            script = generate_script(account, trend, template, style_ref, client_brief, API_KEY)
            results.append(build_output_entry(match, script))
        except RuntimeError as e:
            print(f"    [ERROR] Script generation failed: {e}")
            print(f"    Saving entry without script.")
            results.append(build_no_match_entry({
                **match,
                "no_match_reason": f"Script generation error: {e}",
            }))

        # Polite rate limiting between accounts
        time.sleep(1)

    # ── Stage 4: Save output ──
    if args.output:
        output_path = OUTPUT_DIR / args.output
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = OUTPUT_DIR / f"results_{timestamp}.json"

    # Strip quality_score before writing — output must conform to output_schema.json
    schema_results = [{k: v for k, v in r.items() if k != "quality_score"} for r in results]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(schema_results, f, indent=2, ensure_ascii=False)

    print_final_summary(results, output_path)


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Content AI Pipeline — SaveKu campaign script generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python pipeline.py                          Full pipeline, all accounts
  python pipeline.py --dry-run                Matching only, no script generation
  python pipeline.py --account account_01     Single account only
  python pipeline.py --output my_results.json Custom output filename
        """,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run context matching only. Print assignments without generating scripts.",
    )
    parser.add_argument(
        "--account",
        type=str,
        metavar="ACCOUNT_ID",
        help="Run pipeline for a single account ID (e.g. account_01)",
    )
    parser.add_argument(
        "--output",
        type=str,
        metavar="FILENAME",
        help="Output filename inside the output/ directory (default: results_<timestamp>.json)",
    )
    args = parser.parse_args()
    run_pipeline(args)


if __name__ == "__main__":
    main()
