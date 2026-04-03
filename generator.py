"""
generator.py — Stage 3: Script generation with draft → critique → score → regen loop.

For each account-trend-template combination:
  Per attempt (max 3: 1 initial + 2 regenerations):
    Pass 1 — Draft:    Generate script with full context injection.
                       On regenerations, score_rationale from the previous
                       attempt is injected as an additional constraint.
    Pass 2 — Critique: Review draft on 6 criteria, get revised version if issues found.
    Pass 3 — Score:    5-dimension numeric scoring. auto_approved=True (score >= 7.0) exits loop.
  Best-scoring script across all attempts is returned.

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

_SCORE_THRESHOLD = 7.0
_MAX_REGEN = 2  # max regeneration attempts after the initial (total attempts = 3)


def generate_script(
    account: dict,
    trend: dict,
    template: dict,
    style_videos: list,
    client_brief: str,
    api_key: str,
) -> dict:
    """
    Runs the draft → critique → score loop for a single account.
    If the score is below threshold, regenerates up to _MAX_REGEN times,
    injecting the previous score_rationale as a correction constraint.
    Returns the highest-scoring script across all attempts.
    """
    handle = account["handle"]
    best_script = None
    best_overall = -1.0
    score_feedback = ""

    for attempt in range(_MAX_REGEN + 1):
        tag = "initial" if attempt == 0 else f"regen {attempt}/{_MAX_REGEN}"

        # Pass 1 — Draft
        print(f"    [{tag}] Pass 1: drafting...")
        draft = _call_claude(
            api_key,
            build_draft_prompt(account, trend, template, style_videos, client_brief, score_feedback),
            context=f"{handle} draft",
        )

        # Pass 2 — Critique
        print(f"    [{tag}] Pass 2: critique...")
        critique_result = _call_claude(
            api_key,
            build_critique_prompt(account, draft, FORBIDDEN_WORDS),
            context=f"{handle} critique",
        )
        issues = critique_result.get("issues_found", [])
        if issues:
            print(f"    {len(issues)} issue(s) found — using revised script.")
            for issue in issues:
                print(f"      - {issue}")
            final_script = critique_result.get("revised_script", draft)
        else:
            print(f"    No issues found — using draft.")
            final_script = draft

        # Pass 3 — Score
        print(f"    [{tag}] Pass 3: scoring...")
        try:
            quality_score = _call_claude(
                api_key,
                build_scoring_prompt(account, final_script, FORBIDDEN_WORDS),
                context=f"{handle} score",
            )
            overall = quality_score.get("overall_score", 0.0)
            approved = quality_score.get("auto_approved", False)
            print(f"    Quality score: {overall}/10 — {'APPROVED' if approved else 'NEEDS REVIEW'}")

            final_script["quality_score"] = quality_score

            if overall > best_overall:
                best_overall = overall
                best_script = final_script

            if approved:
                break  # Good enough — stop early

            if attempt < _MAX_REGEN:
                score_feedback = quality_score.get("score_rationale", "")
                print(f"    Below threshold ({_SCORE_THRESHOLD}) — regenerating with feedback...")

        except RuntimeError as e:
            print(f"    [WARN] Scoring failed: {e}")
            final_script["quality_score"] = None
            if best_script is None:
                best_script = final_script
            break

    return best_script


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
