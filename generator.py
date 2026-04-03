"""
generator.py — Stage 3: Script generation with draft + critique loop.

For each account-trend-template combination:
  Pass 1 — Draft:   Generate initial script with full context injection
  Pass 2 — Critique: Review draft for quality issues, get revised version
  Pass 3 — Select:   Use revised script if issues were found, draft if clean

LLM calls go through claude_query.mjs via subprocess.
That script uses the Claude Agent SDK TypeScript (claude binary).
"""

import json
import os
import re
import subprocess
import time
from pathlib import Path

from prompts import build_draft_prompt, build_critique_prompt, build_scoring_prompt, FORBIDDEN_WORDS

BASE_DIR = Path(__file__).parent


# ─── Main function ────────────────────────────────────────────────────────────

def generate_script(
    account: dict,
    trend: dict,
    template: dict,
    style_videos: list,
    client_brief: str,
    api_key: str,
) -> dict:
    """
    Runs the two-pass generation loop for a single account.
    Returns a script dict matching output_schema.json's script.sections structure.
    """
    handle = account["handle"]

    # Pass 1 — Draft
    print(f"    Pass 1: drafting script for {handle}...")
    draft_prompt = build_draft_prompt(account, trend, template, style_videos, client_brief)
    draft = _call_claude(api_key, draft_prompt, context=f"{handle} draft")

    # Pass 2 — Critique
    print(f"    Pass 2: critiquing script for {handle}...")
    critique_prompt = build_critique_prompt(account, draft, FORBIDDEN_WORDS)
    critique_result = _call_claude(api_key, critique_prompt, context=f"{handle} critique")

    # Pass 3 — Select final
    issues = critique_result.get("issues_found", [])
    if issues:
        print(f"    {len(issues)} issue(s) found — using revised script.")
        for issue in issues:
            print(f"      - {issue}")
        final_script = critique_result.get("revised_script", draft)
    else:
        print(f"    No issues found — using draft.")
        final_script = draft

    # Pass 4 — Quality scoring
    print(f"    Pass 3: quality scoring for {handle}...")
    scoring_prompt = build_scoring_prompt(account, final_script, FORBIDDEN_WORDS)
    try:
        quality_score = _call_claude(api_key, scoring_prompt, context=f"{handle} score")
        overall = quality_score.get("overall_score", 0.0)
        approved = quality_score.get("auto_approved", False)
        status = "APPROVED" if approved else "NEEDS REVIEW"
        print(f"    Quality score: {overall}/10 — {status}")
    except RuntimeError as e:
        print(f"    [WARN] Scoring failed, skipping: {e}")
        quality_score = None

    # Embed quality score in script dict (pipeline.py will extract it to output entry level)
    final_script["quality_score"] = quality_score

    return final_script


# ─── Style reference matching ─────────────────────────────────────────────────

def find_style_ref(style_refs: dict, niche_tags: list) -> list:
    """
    Find the best matching category in style_references.json by niche_tag overlap.
    Returns the list of video dicts for the best-matching category.
    Falls back to the first category's videos if no overlap is found.
    """
    best_videos = None
    best_overlap = 0
    trend_tags = set(niche_tags)

    for _category_name, category in style_refs.items():
        ref_tags = set(category.get("niche_tags", []))
        overlap = len(ref_tags & trend_tags)
        if overlap > best_overlap:
            best_overlap = overlap
            best_videos = category.get("videos", [])

    if best_videos is None:
        first_category = next(iter(style_refs.values()))
        best_videos = first_category.get("videos", [])

    return best_videos


# ─── Claude Agent SDK call via subprocess ────────────────────────────────────

def _call_claude(api_key: str, prompt: str, context: str = "", retries: int = 3) -> dict:
    """
    Pipes prompt to claude_query.mjs via stdin.
    That script uses the Claude Agent SDK TypeScript (claude binary) to get a result.
    ANTHROPIC_API_KEY is injected into the subprocess environment.
    Retries up to `retries` times with exponential backoff.
    Raises RuntimeError after all retries are exhausted.
    """
    env = os.environ.copy()  # claude binary uses auth from claude login

    last_error = None

    for attempt in range(1, retries + 1):
        try:
            proc = subprocess.run(
                ["node", str(BASE_DIR / "claude_query.mjs")],
                input=prompt,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=300,
                env=env,
            )

            if proc.returncode != 0:
                raise RuntimeError(proc.stderr.strip() or f"exit code {proc.returncode}")

            return _parse_json(proc.stdout)

        except subprocess.TimeoutExpired:
            last_error = "subprocess timed out after 300s"
        except json.JSONDecodeError as e:
            last_error = f"JSON parse error: {e} | raw output: {proc.stdout[:200]!r}"
        except RuntimeError as e:
            last_error = str(e)
        except Exception as e:
            last_error = str(e)

        if attempt < retries:
            wait = 2 ** attempt  # 2s, 4s
            print(f"    [{context}] Attempt {attempt} failed — retrying in {wait}s...\n      Error: {last_error}")
            time.sleep(wait)

    raise RuntimeError(
        f"Claude call failed after {retries} attempts [{context}]: {last_error}"
    )


def _parse_json(text: str) -> dict:
    """
    Strip markdown code fences (```json...``` or ```...```) then parse JSON.
    """
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)
    return json.loads(text.strip())
