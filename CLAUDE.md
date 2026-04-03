# Content AI Pipeline — Project Context

## What This Is

A CLI-based content generation pipeline for **CAKAI Software Engineer Assessment**.
Fictional client: **SaveKu** — an Indonesian fintech app launching a micro-savings product (Rp 5,000/day).
Goal: generate ready-to-post social media scripts for 4 niche accounts, each matched to a trending topic.

---

## Project Structure

```
Content-AI/
├── pipeline.py            # CLI entry point — orchestrates all 4 stages
├── matcher.py             # Stage 1 & 2: trend matching + template selection
├── generator.py           # Stage 3: draft + critique loop per account
├── prompts.py             # All prompt builders (match, draft, critique)
├── claude_query.mjs       # Node.js ESM — Claude Agent SDK bridge (stdin→stdout)
├── package.json           # npm: @anthropic-ai/claude-agent-sdk
├── style_references.json  # Manual TikTok transcripts grouped by niche category
├── accounts.json          # 4 account profiles (provided)
├── client_brief.md        # SaveKu brand voice, forbidden words, CTA rules (provided)
├── templates.json         # 3 content template schemas (provided)
├── trends.json            # 6 trending topics (provided)
├── output_schema.json     # Required output JSON schema (provided)
├── output/                # Generated results go here (results_<timestamp>.json)
├── requirements.txt       # Python: python-dotenv
├── .env                   # No API key needed — auth via claude login
└── test_api.py            # Smoke test for the Claude Agent SDK bridge
```

---

## Architecture

```
pipeline.py (Python orchestrator)
    │
    ├── Stage 1+2: matcher.py
    │     └── _call_claude() → node claude_query.mjs (stdin/stdout)
    │                               └── Claude Agent SDK TypeScript
    │                                     └── claude binary (Claude Code CLI)
    │
    └── Stage 3: generator.py (per account)
          ├── Pass 1: _call_claude() → draft script
          ├── Pass 2: _call_claude() → critique + revise
          └── Pass 3: select final (revised if issues found, draft if clean)
```

### LLM Layer

All LLM calls go through `claude_query.mjs`:
- Python pipes the prompt via **stdin**
- Node.js runs the Claude Agent SDK `query()` with `tools: []` (pure text generation)
- Result comes back via **stdout**
- Auth uses `claude login` — no API key in code or env

### Key Design: No API Key Required

`claude_query.mjs` uses the `claude` binary installed on the machine.
Auth is handled by `claude login` (OAuth). `.env` file is empty / unused.

---

## The 4 Stages

### Stage 1 — Context Matching (`matcher.py`)
- Single LLM call with all 4 accounts + 6 trends + 3 templates
- Returns scored matches with explicit rationale per account
- Falls back to `FALLBACK_MATCHES` (hardcoded, pre-analyzed) if LLM fails

**Pre-analyzed matches (fallback):**
| Account | Trend | Template | Score |
|---|---|---|---|
| @jakartafoodcraving | trend_02 (hidden gems warung under 20k) | template_trend_hijack | 0.95 |
| @budgetbuddysby | trend_01 (gaji 8 juta cukup ga sih) | template_relatable_struggle | 0.90 |
| @bandungdaydream | trend_05 (cafe Bandung yang belum rame) | template_trend_hijack | 0.92 |
| @ngobrolbisnis | trend_04 (first year bisnis jangan gini) | template_relatable_struggle | 0.93 |

### Stage 2 — Template Selection (`matcher.py`)
Handled in the same single LLM call as Stage 1.

### Stage 3 — Script Generation (`generator.py`)
Per account, 3-pass loop:
1. **Draft** — `build_draft_prompt()` injects: style reference transcripts, tone tokens from account profile, few-shot good/bad examples, anti-prompt (forbidden words + formal Indonesian), template structure, trend context, client brief
2. **Critique** — `build_critique_prompt()` reviews for: spoken-word naturalness, forbidden words, CTA quality, slang authenticity, product reveal timing, brand voice
3. **Select** — uses revised script if issues found, draft if clean
4. **Score** — `build_scoring_prompt()` produces 5-dimension numeric score (slang_authenticity, spoken_naturalness, brand_compliance, product_integration, hook_strength) with overall_score (0–10) and `auto_approved` flag (true if ≥ 7.0)

### Stage 4 — Structured Output (`pipeline.py`)
Saves to `output/results_<timestamp>.json` matching `output_schema.json`.

---

## Prompt Quality Techniques (from `prompts.py`)

1. **Style Reference Injection** — `style_references.json` has manually transcribed TikTok videos grouped by niche (5 per category, 20 total). Matched by tag overlap, all real transcripts injected as numbered references. Claude copies the cadence, not the content.

2. **Tone Token Injection** — Slang phrases extracted from `accounts.json` tone field (e.g. `['gila sih', 'ini real']`), injected as mandatory natural usage.

3. **Few-Shot Prompting** — One BAD example (formal, ad-like) and one GOOD example (casual, spoken, relatable) injected before every draft call.

4. **Anti-Prompt** — Hard `DO NOT` list: formal connectors (`merupakan`, `adalah`), ad openers, all client forbidden words, sentences longer than one breath.

5. **Critique Agent** — Second LLM pass reviews the draft on 6 criteria and returns a revised version if issues are found.

6. **Quality Scoring** — Third LLM pass (`build_scoring_prompt()`) scores the final script on 5 weighted dimensions, returns `overall_score` (0–10) and `auto_approved` (true if ≥ 7.0). Score is saved at output entry level (`quality_score` field).

---

## Style References (`style_references.json`)

Format: dict keyed by category, each with `niche_tags` and `videos[]`.

```json
{
  "jakarta_food_review": {
    "niche_tags": ["street food", "jakarta food", ...],
    "videos": [
      { "id": "...", "niche": "...", "visual_cuts": "...", "transcript": "..." }
    ]
  }
}
```

Matching: `find_style_ref(style_refs, trend_niche_tags)` returns the video list for the category with the most tag overlap. All videos with real transcripts are injected into the draft prompt.

Currently filled categories: `jakarta_food_review`, `bandung_aesthetic_vlog`, `business_advice_warung`, `finance_talk`.

---

## CLI Usage

```bash
# Full pipeline
python pipeline.py

# Match only (no LLM script calls)
python pipeline.py --dry-run

# Single account
python pipeline.py --account account_01

# Custom output filename
python pipeline.py --output my_results.json
```

---

## Running the Pipeline

```bash
# 1. Install Python deps
pip install -r requirements.txt

# 2. Install Node deps (Claude Agent SDK)
npm install

# 3. Make sure claude binary is logged in
claude login

# 4. Smoke test
python test_api.py

# 5. Run
python pipeline.py --dry-run
python pipeline.py
```

---

## Edge Cases Handled

| Scenario | Handling |
|---|---|
| No trend fits account (score < 0.5) | `trend_id: null`, `no_match_reason` filled, no script |
| LLM matching call fails | Falls back to `FALLBACK_MATCHES` in `matcher.py` |
| Script generation fails | Entry saved with `no_match_reason`, pipeline continues |
| Critique finds issues | Revised script used |
| Critique finds no issues | Draft used as-is |
| Style ref transcript is placeholder | Draft prompt falls back to account tone description |
| Claude subprocess times out (300s) | Retried up to 3 times with exponential backoff |

---

## Files NOT to Modify

- `accounts.json`, `client_brief.md`, `templates.json`, `trends.json`, `output_schema.json` — provided assessment inputs
- `.env` — user-specific, not committed

## Files to Modify When Extending

- `style_references.json` — add more video references per category
- `prompts.py` — tune prompt quality (few-shot examples, anti-prompt list)
- `matcher.py` → `FALLBACK_MATCHES` — update if accounts/trends change
