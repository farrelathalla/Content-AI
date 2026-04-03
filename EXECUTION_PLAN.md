# Content AI Pipeline — Execution Plan

Step-by-step build order. Each step is small and testable before moving on.

---

## Step 0 — Setup (5 min)

```bash
pip install google-genai
```

Create `requirements.txt`:
```
google-genai
```

Set your API key — either hardcode in `pipeline.py` (like `script.py` does) or use env var:
```bash
export GEMINI_API_KEY="your_key_here"
```

---

## Step 1 — Create `style_references.json` (~20 min, manual)

**Do this before writing code.** Go to TikTok and find:

1. A fast-paced Jakarta street food video (search: "warung murah Jakarta challenge")
2. A dreamy Bandung cafe vlog (search: "cafe Bandung aesthetic reels")
3. An entrepreneur telling a first-year mistake story (search: "kesalahan bisnis pertama TikTok")
4. A casual salary/expense breakdown (search: "gaji 8 juta cukup ga")

For each: transcribe the **first 15–20 seconds of spoken dialogue only**. Note the visual style in 1 sentence.

Fill in `style_references.json` using the structure in the Implementation Plan.

---

## Step 2 — Create `prompts.py`

This file holds all prompt templates as Python string constants. Keeps the logic files clean.

**Constants to define:**

```python
MATCH_PROMPT          # Trend + template matching for all accounts
SCRIPT_DRAFT_PROMPT   # First-pass script generation (includes few-shot, tone tokens, anti-prompt, style ref)
SCRIPT_CRITIQUE_PROMPT  # Second-pass critique and rewrite
```

### `MATCH_PROMPT` structure:
```
You are a content strategist for an Indonesian social media agency.

ACCOUNTS:
{accounts_json}

TRENDS:
{trends_json}

TEMPLATES:
{templates_json}

For each account:
1. Score every trend 0.0–1.0 based on: niche alignment, audience demographics, regional fit, format compatibility
2. Pick the highest-scoring trend
3. From the 3 templates, pick the best fit for this account-trend pair based on account tone and template best_for field
4. Write a 2-sentence trend_match_rationale (cite specific account + trend attributes)
5. Write a 1-sentence template_selection_rationale
6. Name the second-best trend option and why it lost (alternative_considered)
7. If best trend score < 0.5: set trend_id to null, fill no_match_reason

Return ONLY a raw JSON array, no markdown, no explanation:
[{
  "account_id": "...",
  "trend_id": "...",         // or null
  "template_id": "...",      // or null
  "fit_score": 0.0,
  "reasoning": {
    "trend_match_rationale": "...",
    "template_selection_rationale": "...",
    "alternative_considered": "..."
  },
  "no_match_reason": null    // or string
}]
```

### `SCRIPT_DRAFT_PROMPT` structure (fill with f-string):
```
You are a native Indonesian content creator writing a script for {handle} on {platform}.

=== ACCOUNT PERSONA ===
Niche: {niche}
Tone: {tone}
Audience: {audience}
Posting style: {posting_style}

=== STYLE REFERENCE (linguistic DNA — cadence, pacing, slang frequency) ===
"{style_transcript}"
Visual style: {style_visual_notes}

Rule: COPY the conversational cadence and pacing. DO NOT copy the topic.

=== CONTENT TEMPLATE ===
Template: {template_name}
Structure: {template_structure_json}

=== CLIENT BRIEF ===
Brand voice: Warm, relatable, slightly self-deprecating. Talks like a financially-aware friend.
Target emotions: "oh that's literally me" recognition → gentle motivation → relief
CTA pattern: End conversationally — question, gentle nudge, or social proof. Never "download now."
Forbidden words: investasi, financial freedom, kebebasan finansial, passive income, grind, hustle, crypto, trading, dijamin, guarantee language

=== TREND TO INCORPORATE ===
Topic: {trend_topic}
Description: {trend_description}
Trending format: {trending_format}

=== SAVEKU PRODUCT ===
SaveKu Tabungan Mikro: daily micro-savings, as low as Rp 5,000/day, auto-deducted from e-wallet.
Frame it as: small, easy, discovered naturally — NOT as the main point of the video.

=== SLANG TOKENS (use at least one naturally) ===
{slang_tokens}

=== FEW-SHOT EXAMPLES ===

BAD (DO NOT write like this):
"Halo teman-teman! Apakah kalian tahu bahwa menabung sangat penting untuk masa depan finansial? Dengan SaveKu, Anda bisa menabung lima ribu rupiah saja setiap harinya untuk meraih kebebasan finansial."
Why it fails: formal Indonesian, sounds like TV ad, uses forbidden phrase, no personality.

GOOD (write like this):
"Sumpah ya, dulu gue mikir nabung tuh nunggu sisa gaji. Ujung-ujungnya? Ya habis buat ngopi aja sih wkwk. Terus nemu cara gampang banget, literally cuma lima ribu sehari..."
Why it works: casual spoken cadence, fragmented sentences, self-deprecating, relatable, product mention feels discovered not sold.

=== DO NOT USE ===
- Formal connectors: merupakan, adalah, oleh karena itu, dengan demikian, adapun
- Ad openers: Halo guys, Welcome back, Apa kabar semuanya, Hai semua
- Ad closers: dapatkan sekarang, segera download, jangan sampai ketinggalan
- All forbidden words listed above
- Perfect grammar — this is spoken word, not an essay
- Sentences longer than one breath (if it takes more than one breath to say, break it)
- Shame about spending or framing saving as sacrifice

=== OUTPUT FORMAT ===
Return ONLY raw JSON, no markdown:
{
  "sections": [
    {
      "section_name": "...",
      "dialogue": "...",
      "estimated_duration_seconds": 0,
      "stage_direction": "..."
    }
  ],
  "total_duration_seconds": 0,
  "language_notes": "..."
}
```

### `SCRIPT_CRITIQUE_PROMPT` structure:
```
You are an expert Indonesian Gen-Z/millennial TikTok content director. You have seen thousands of scripts fail because they sound written, not spoken.

Review this script for {handle}:

{draft_script_json}

Evaluate against these criteria:
1. SPOKEN WORD TEST: Read each line aloud mentally. Flag any line that sounds like it was written for a reader, not spoken to a phone camera.
2. FORBIDDEN WORDS: Check against this list: {forbidden_words}
3. CTA CHECK: Does the ending feel like a friend finishing a story, or like an ad?
4. SLANG TEST: Are the account's slang tokens ({slang_tokens}) used naturally, not forced?
5. PRODUCT REVEAL: Is the product mentioned too early, too obviously, or too much?
6. BRAND VOICE: Never preachy, never condescending about spending. Is this maintained?

Output format — return raw JSON only:
{
  "issues_found": ["issue 1", "issue 2"],   // empty array if none
  "revised_script": { same structure as input script }
}

If no issues are found, return the original script unchanged in revised_script.
```

---

## Step 3 — Create `matcher.py`

**Function:** `run_matching(accounts, trends, templates, client) -> list[dict]`

```python
def run_matching(accounts, trends, templates, client):
    # 1. Build the match prompt (inject all JSON data)
    # 2. Call Gemini once
    # 3. Parse JSON response
    # 4. Validate: check all 4 accounts are present, scores are 0–1
    # 5. On failure: use hardcoded fallback (see Implementation Plan table)
    # 6. Return list of match objects
```

**Hardcoded fallback** (import-time constant, not a runtime call):
```python
FALLBACK_MATCHES = [
    {"account_id": "account_01", "trend_id": "trend_02", "template_id": "template_trend_hijack", "fit_score": 0.95, ...},
    {"account_id": "account_02", "trend_id": "trend_01", "template_id": "template_relatable_struggle", "fit_score": 0.90, ...},
    {"account_id": "account_03", "trend_id": "trend_05", "template_id": "template_trend_hijack", "fit_score": 0.92, ...},
    {"account_id": "account_04", "trend_id": "trend_04", "template_id": "template_relatable_struggle", "fit_score": 0.93, ...},
]
```

**Test after this step:**
```bash
python -c "from matcher import run_matching; print('matcher imports OK')"
```

---

## Step 4 — Create `generator.py`

**Function:** `generate_script(account, trend, template, style_ref, client) -> dict`

```python
def generate_script(account, trend, template, style_ref, client):
    # Pass 1: Draft
    draft_prompt = build_draft_prompt(account, trend, template, style_ref)
    draft = call_gemini(client, draft_prompt)
    
    # Pass 2: Critique
    critique_prompt = build_critique_prompt(account, draft)
    critique_result = call_gemini(client, critique_prompt)
    
    # Pass 3: Select final
    if critique_result["issues_found"]:
        final_script = critique_result["revised_script"]
    else:
        final_script = draft
    
    return final_script
```

**Helper:** `call_gemini(client, prompt, retries=3) -> dict`
- Wraps the Gemini call with retry logic
- Enforces `response_mime_type="application/json"`
- On failure after retries: raises with clear message

**Helper:** `find_style_ref(style_refs, niche_tags) -> dict`
- Finds the best matching style reference by overlapping niche_tags
- Falls back to first reference if no match

**Test after this step:** Generate one script manually in a test file before wiring to pipeline.

---

## Step 5 — Create `pipeline.py`

**Main orchestration + CLI.**

```python
import argparse
import json
import time
from pathlib import Path
from google import genai
from google.genai import types

from matcher import run_matching
from generator import generate_script

def load_inputs():
    # Load all 5 JSON/MD files
    # Parse client_brief.md as plain text (inject as string into prompts)
    pass

def run_pipeline(args):
    client = genai.Client(api_key=API_KEY)
    
    accounts, trends, templates, style_refs, client_brief = load_inputs()
    
    # Filter to single account if --account flag used
    if args.account:
        accounts = [a for a in accounts if a["id"] == args.account]
    
    print("Running context matching...")
    matches = run_matching(accounts, trends, templates, client)
    
    if args.dry_run:
        print_match_summary(matches)
        return
    
    results = []
    for match in matches:
        account = get_by_id(accounts, match["account_id"])
        
        if match["trend_id"] is None:
            print(f"  {account['handle']}: no trend match — {match['no_match_reason']}")
            results.append(build_no_match_output(match))
            continue
        
        trend = get_by_id(trends, match["trend_id"])
        template = get_by_id(templates, match["template_id"])
        style_ref = find_style_ref(style_refs, trend["niche_tags"])
        
        print(f"  {account['handle']}: generating script ({trend['topic']})...")
        script = generate_script(account, trend, template, style_ref, client)
        
        time.sleep(1)  # polite rate limiting between accounts
        
        results.append(build_output(match, script))
    
    save_output(results, args.output)
    print_summary(results)

def main():
    parser = argparse.ArgumentParser(description="Content AI Pipeline — SaveKu")
    parser.add_argument("--dry-run", action="store_true", help="Match only, no script generation")
    parser.add_argument("--account", type=str, help="Run for single account ID only")
    parser.add_argument("--output", type=str, default=None, help="Output filename")
    args = parser.parse_args()
    run_pipeline(args)

if __name__ == "__main__":
    main()
```

---

## Step 6 — Wire Everything Together & Test

### Test sequence:

**Test 1 — Dry run (matching only):**
```bash
python pipeline.py --dry-run
```
Expected: prints 4 account → trend → template assignments with scores. No Gemini draft calls.

**Test 2 — Single account:**
```bash
python pipeline.py --account account_01
```
Expected: runs matching, generates 1 script, saves output JSON. Check:
- Script is in Bahasa Indonesia
- No forbidden words
- Dialogue sounds spoken, not written
- `stage_direction` filled for each section
- `total_duration_seconds` is reasonable (25–40 seconds)

**Test 3 — Full pipeline:**
```bash
python pipeline.py
```
Expected: 4 scripts generated, saved to `output/results_<timestamp>.json`

**Test 4 — Output validation:**
Manually compare output JSON against `output_schema.json`. Check:
- All required fields present
- `fit_score` between 0 and 1
- `no_match_reason` is null when match exists
- `script` is null when no match

---

## Step 7 — Quality Check Each Script

For each of the 4 generated scripts, manually verify:

**Checklist:**
- [ ] Could this actually be posted on the account's platform?
- [ ] Does it feel like it belongs on that specific account?
- [ ] No forbidden words (investasi, financial freedom, passive income, grind, dijamin, crypto/trading)
- [ ] CTA sounds like a friend, not an ad
- [ ] Product mention feels natural, not central
- [ ] Account's slang tokens appear at least once
- [ ] No formal Indonesian connectors (merupakan, adalah, etc.)
- [ ] No sentence takes more than one breath to say

If a script fails the checklist, adjust the prompts in `prompts.py` and re-run that account.

---

## Step 8 — Edge Case Testing

**Test: force a no-match scenario**

Temporarily add a 5th account with a completely unrelated niche (e.g., gaming/esports) to `accounts.json` and run the pipeline. Verify:
- Output has `trend_id: null`
- `no_match_reason` is a coherent explanation
- No script is generated for it
- The JSON is still valid and complete

Remove the test account after verifying.

---

## Step 9 — Final Output Check

```bash
python pipeline.py --output final_results.json
cat output/final_results.json | python -m json.tool  # validate JSON syntax
```

Confirm the file is valid JSON and matches `output_schema.json`.

---

## Step 10 — Write README

Cover (as required by brief):
1. How to run it
2. Design choices (why Gemini, why 9 calls, why static RAG, why critique agent)
3. What you'd improve with more time
4. How this changes at 50+ accounts

---

## File Creation Order

```
1. style_references.json     (manual, do first)
2. prompts.py                (all prompt constants)
3. matcher.py                (Stage 1 + 2)
4. generator.py              (Stage 3)
5. pipeline.py               (orchestration + CLI)
6. requirements.txt          (google-genai)
7. README.md                 (last)
```

---

## Time Estimate Per Step

| Step | Task | Notes |
|---|---|---|
| 0 | Setup | Install deps, API key |
| 1 | style_references.json | Manual TikTok research — most important for quality |
| 2 | prompts.py | Longest step — prompt quality determines output quality |
| 3 | matcher.py | Relatively straightforward |
| 4 | generator.py | Medium complexity |
| 5 | pipeline.py | Wiring + CLI args |
| 6 | Test + fix | Expect 2–3 prompt iterations |
| 7 | Quality check | Read each script carefully |
| 8 | Edge cases | Quick |
| 9 | Final output | Quick |
| 10 | README | Last |
