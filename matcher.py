"""
matcher.py — Stage 1 & 2: Context matching and template selection.

Sends a single Claude call for all accounts to get:
- Best trend per account
- Best template per account-trend pair
- Explicit reasoning for each decision

Falls back to hardcoded scores if the API call fails.
"""

import json
from prompts import build_match_prompt
from generator import _call_claude


# ─── Hardcoded fallback ───────────────────────────────────────────────────────
# Pre-analyzed matches used if Gemini call fails or returns malformed JSON.
# Derived from manual analysis in IMPLEMENTATION_PLAN.md.

FALLBACK_MATCHES = [
    {
        "account_id": "account_01",
        "trend_id": "trend_02",
        "template_id": "template_trend_hijack",
        "fit_score": 0.95,
        "reasoning": {
            "trend_match_rationale": (
                "trend_02 ('hidden gems warung under 20k') is a direct niche match for "
                "@jakartafoodcraving — both are Jakarta-based food discovery content targeting "
                "the same food-obsessed Gen-Z/millennial audience. The multi-spot crawl format "
                "maps perfectly to the account's fast-paced, visual food narration style."
            ),
            "template_selection_rationale": (
                "template_trend_hijack fits because the account has a strong personality voice "
                "and the trend has clear algorithmic momentum to ride — the trend is the vehicle, "
                "the account's niche perspective is the payload."
            ),
            "alternative_considered": (
                "trend_01 ('gaji 8 juta cukup ga sih') was considered but rejected — "
                "finance content is outside this account's food niche and would feel off-brand."
            ),
        },
        "no_match_reason": None,
    },
    {
        "account_id": "account_02",
        "trend_id": "trend_01",
        "template_id": "template_relatable_struggle",
        "fit_score": 0.90,
        "reasoning": {
            "trend_match_rationale": (
                "trend_01 ('gaji 8 juta cukup ga sih') aligns directly with @budgetbuddysby's "
                "niche of practical money tips for young professionals, and the expense breakdown "
                "debate format suits the account's talking-head, listicle-style posting style. "
                "The audience demographic (24-32, early career, 5-10M/month earners) overlaps "
                "perfectly with the trend's viral discussion."
            ),
            "template_selection_rationale": (
                "template_relatable_struggle fits because the audience resists hard sells and "
                "responds to content that makes them feel understood first — the struggle-to-pivot "
                "structure mirrors the expense breakdown narrative naturally."
            ),
            "alternative_considered": (
                "trend_06 ('nabung 100rb sehari challenge') was considered but the 100k/day "
                "framing conflicts with SaveKu's 5k/day micro-savings product — too large a gap "
                "creates a credibility issue for the product reveal."
            ),
        },
        "no_match_reason": None,
    },
    {
        "account_id": "account_03",
        "trend_id": "trend_05",
        "template_id": "template_trend_hijack",
        "fit_score": 0.92,
        "reasoning": {
            "trend_match_rationale": (
                "trend_05 ('cafe Bandung yang belum rame') is an exact region and niche match for "
                "@bandungdaydream — both are Bandung-based aesthetic cafe content for the same "
                "Gen-Z creative audience. The dreamy visual cafe tour format is the account's "
                "native posting style."
            ),
            "template_selection_rationale": (
                "template_trend_hijack fits because the Bandung cafe trend has strong local "
                "algorithmic traction and the account's dreamy aesthetic voice gives it a "
                "distinctive angle within the crowded trend."
            ),
            "alternative_considered": (
                "trend_03 ('romanticize your boring life') was a close second due to aesthetic "
                "and soft-life overlap, but trend_05 has higher regional specificity and active "
                "peak window making it more timely."
            ),
        },
        "no_match_reason": None,
    },
    {
        "account_id": "account_04",
        "trend_id": "trend_04",
        "template_id": "template_relatable_struggle",
        "fit_score": 0.93,
        "reasoning": {
            "trend_match_rationale": (
                "trend_04 ('first year bisnis jangan gini') is an exact niche match for "
                "@ngobrolbisnis — both target aspiring and early-stage entrepreneurs in Java. "
                "The mistake-storytelling monologue format maps directly to the account's "
                "face-to-camera monologue with strong opening hook and lesson structure."
            ),
            "template_selection_rationale": (
                "template_relatable_struggle fits because the first-year mistake narrative "
                "follows the struggle-escalation-pivot-reveal arc naturally, and the account's "
                "mentor-at-warung-kopi tone works best when the audience feels seen before "
                "receiving advice."
            ),
            "alternative_considered": (
                "template_soft_tutorial was considered but rejected — @ngobrolbisnis builds "
                "trust through storytelling, not instructional lists, and the trend's emotional "
                "format is better served by the struggle structure."
            ),
        },
        "no_match_reason": None,
    },
]


# ─── Main function ────────────────────────────────────────────────────────────

def run_matching(accounts: list, trends: list, templates: list, api_key: str) -> list:
    """
    Match each account to the best trend and template using a single Kimi K2.5 call.
    Falls back to FALLBACK_MATCHES if the API call fails or returns invalid data.

    Returns a list of match dicts conforming to output_schema.json fields:
    account_id, trend_id, template_id, fit_score, reasoning, no_match_reason
    """
    print("  Calling Claude for context matching...")

    try:
        prompt = build_match_prompt(accounts, trends, templates)
        matches = _call_claude(api_key, prompt, context="matching")
        _validate_matches(matches, accounts)
        print(f"  Claude matching succeeded for {len(matches)} accounts.")
        return matches

    except Exception as e:
        print(f"  Claude matching failed ({e}). Using fallback matches.")
        return FALLBACK_MATCHES


# ─── Validation ───────────────────────────────────────────────────────────────

def _validate_matches(matches: list, accounts: list):
    """
    Raises ValueError if the API response is missing accounts or has invalid scores.
    Triggers fallback in run_matching.
    """
    if not isinstance(matches, list):
        raise ValueError("Response is not a list")

    account_ids = {a["id"] for a in accounts}
    returned_ids = {m.get("account_id") for m in matches}

    if not account_ids.issubset(returned_ids):
        missing = account_ids - returned_ids
        raise ValueError(f"Missing accounts in API response: {missing}")

    for m in matches:
        score = m.get("fit_score")
        if score is None or not (0.0 <= float(score) <= 1.0):
            raise ValueError(f"Invalid fit_score for {m.get('account_id')}: {score}")
