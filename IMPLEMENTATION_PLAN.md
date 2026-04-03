# Content AI Pipeline — Implementation Plan

## Overview

A CLI-based Python pipeline that takes structured inputs (client brief, account profiles, trends, templates) and produces ready-to-post social media scripts, each matched to the right account with transparent reasoning. Uses Google Gemini API (free tier).

---

## Project Structure

```
Content-AI/
├── pipeline.py              # CLI entry point — orchestrates the full pipeline
├── matcher.py               # Stage 1 & 2: trend matching + template selection
├── generator.py             # Stage 3: script generation (draft + critique loop)
├── style_references.json    # Manual transcript references for few-shot style injection
├── prompts.py               # All prompt templates as constants (keeps pipeline.py clean)
├── accounts.json            # (provided)
├── client_brief.md          # (provided)
├── templates.json           # (provided)
├── trends.json              # (provided)
├── output_schema.json       # (provided)
├── output/                  # Generated outputs saved here
│   └── results_<timestamp>.json
└── requirements.txt
```

---

## Data Flow

```
Load inputs (JSON + MD)
        │
        ▼
[Stage 1] Context Matching (matcher.py)
  For each account → score every trend → pick best fit
  Reasoning: explicit rationale string per account
        │
        ▼
[Stage 2] Template Selection (matcher.py)
  For each account-trend pair → score templates → pick best
  Reasoning: explicit rationale string
        │
        ▼
[Stage 3] Script Generation (generator.py)
  Per account: Draft → Critique → Refine
  Injects: tone tokens, few-shot examples, anti-prompt, style reference
        │
        ▼
[Stage 4] Structured Output
  Assemble output_schema.json-compliant JSON
  Print CLI summary + save to output/results_<timestamp>.json
```

---

## Stage 1 — Context Matching (`matcher.py`)

### Goal
For each account, find the best-fitting trend. Reasoning must be visible, not a black box.

### Approach: Gemini-Assisted Scoring
Send a single Gemini call with all 4 accounts and all 6 trends. Ask it to return a scored match table with explicit rationale per pair. This is faster than 4 × 6 = 24 calls and gives comparative reasoning.

### Prompt Strategy
```
Given these account profiles and trending topics, for each account:
1. Score every trend from 0.0–1.0 based on niche alignment, audience match, and regional fit
2. Pick the best match
3. Write a 2-sentence rationale explaining WHY (reference specific account attributes and trend attributes)
4. Name the second-best option and why it lost

Return as JSON matching this schema: [{ account_id, trend_id, fit_score, trend_match_rationale, alternative_considered }]
```

### Pre-Analysis (hardcoded fallback if Gemini fails)
| Account | Best Trend | Fit Score | Reason |
|---|---|---|---|
| @jakartafoodcraving | trend_02 (hidden gems warung under 20k) | 0.95 | Same niche (Jakarta food), same format (challenge/crawl), same audience |
| @budgetbuddysby | trend_01 (gaji 8 juta cukup ga sih) | 0.90 | Finance niche + young professionals in major cities, expense breakdown format fits talking-head style |
| @bandungdaydream | trend_05 (cafe Bandung yang belum rame) | 0.92 | Exact region match (Bandung), aesthetic cafe content = core niche |
| @ngobrolbisnis | trend_04 (first year bisnis jangan gini) | 0.93 | Exact niche match (entrepreneurship), storytelling monologue = account's posting style |

### Edge Cases
- If Gemini returns a score below 0.5 for all trends for an account → mark as `no_match`, output `no_match_reason` explaining the gap
- If Gemini call fails → use hardcoded fallback scores above

---

## Stage 2 — Template Selection (`matcher.py`)

### Goal
For each account-trend pair, choose the most appropriate content template.

### Selection Logic
Run inside the same Gemini call as Stage 1, or as a follow-up call. Ask Gemini to choose from `template_relatable_struggle`, `template_trend_hijack`, `template_soft_tutorial` based on:
- Account tone (dramatic vs calm vs dreamy vs direct)
- Trend format (crawl challenge vs expense breakdown vs montage vs monologue)
- Template's `best_for` field

### Pre-Analysis
| Account | Template | Rationale |
|---|---|---|
| @jakartafoodcraving | template_trend_hijack | Trend is a food challenge — hijack it. Account has strong personality voice. |
| @budgetbuddysby | template_relatable_struggle | Expense breakdown debate = relatable struggle. Audience resists hard sells. |
| @bandungdaydream | template_trend_hijack | Ride the Bandung cafe trend. Dreamy visuals = perfect trend hijack vehicle. |
| @ngobrolbisnis | template_relatable_struggle | Mistake storytelling maps directly to Struggle → Pivot → Reveal structure. |

---

## Stage 3 — Script Generation (`generator.py`)

This is the core quality layer. Uses 5 techniques from the strategy docs.

### Technique 1: Style Reference Injection (RAG-style)
`style_references.json` stores 3–4 manually transcribed TikTok video excerpts:
- One fast-paced Jakarta food review
- One dreamy Bandung aesthetic vlog
- One no-nonsense business advice video
- One casual personal finance breakdown

The generator pulls the matching reference by niche tag and injects it into the prompt as a "linguistic DNA sample."

**Prompt structure:**
```
Reference Transcript (style only, do NOT copy the topic):
"[TRANSCRIPT PLACEHOLDER]"

Analyze its: sentence length, breathing rhythm, filler words, pacing, slang frequency.
Using EXACTLY that cadence, write a new script about [SaveKu + niche topic].
```

### Technique 2: Tone Token Injection
Programmatically extract exact slang phrases from `accounts.json` per account and inject as mandatory usage:

```
You MUST naturally use at least ONE of these exact phrases from this account's voice: ['gila sih', 'ini real']
Do not force them — find the natural moment in the script.
```

### Technique 3: Few-Shot Prompting (Good vs Bad)
Inject one BAD example and one GOOD example before every script generation call:

**BAD (what to avoid):**
> "Halo teman-teman! Apakah kalian tahu bahwa menabung sangat penting untuk masa depan? Dengan SaveKu, Anda bisa menabung lima ribu rupiah saja setiap hari." ← too formal, sounds like a TV ad, uses "adalah"-style structure

**GOOD (what to aim for):**
> "Sumpah ya, dulu gue mikir nabung tuh nunggu sisa gaji. Ujung-ujungnya? Ya habis buat ngopi aja sih wkwk. Terus nemu cara gampang banget, literally cuma lima ribu sehari..."

### Technique 4: Anti-Prompt (Negative Constraints)
Hard list of DO NOTs injected into every prompt:

```
DO NOT use:
- Formal connectors: 'merupakan', 'adalah', 'oleh karena itu', 'dengan demikian'
- Openers: 'Halo guys', 'Welcome back', 'Apa kabar semuanya'
- Ad-speak: 'dapatkan sekarang', 'segera download', 'jangan lewatkan'
- Forbidden words from client brief: 'investasi', 'financial freedom', 'passive income', 'grind', 'dijamin'
- Crypto/trading references
- Any guarantee language
- Never shame spending habits
- Never frame saving as sacrifice
```

### Technique 5: Critique Agent (Multi-Pass Generation)

**Pass 1 — Draft:**
Generate the initial script using all context above.

**Pass 2 — Critique:**
Send the draft back to Gemini with this critique prompt:
```
You are an expert Indonesian Gen-Z/millennial content director with 5 years on TikTok/Reels.

Review this script:
[DRAFT]

Check for:
1. Does any line sound like it was written, not spoken? Flag it.
2. Any forbidden words from the client brief?
3. Does the CTA sound like an ad or like a friend ending a conversation?
4. Does it naturally use the account's slang tokens?
5. Is the product reveal too obvious / too early?

Output: list of specific issues found, then a revised version fixing each issue.
```

**Pass 3 — Final:**
Use the revised script. If no issues were found in Pass 2, use the draft directly.

### Stage Directions
For each script section, the generator also fills `stage_direction` based on account type:
- @jakartafoodcraving → fast cuts, price tag overlays, reaction shots
- @budgetbuddysby → talking head, text overlay, relatable reaction face
- @bandungdaydream → slow-mo close-ups, soft focus, text fades in gently
- @ngobrolbisnis → face-to-camera, lean-in for emphasis, warung kopi setting

---

## Stage 4 — Structured Output

Assembles the final array of objects matching `output_schema.json`:

```json
[
  {
    "account_id": "account_01",
    "trend_id": "trend_02",
    "template_id": "template_trend_hijack",
    "reasoning": {
      "trend_match_rationale": "...",
      "template_selection_rationale": "...",
      "alternative_considered": "..."
    },
    "fit_score": 0.95,
    "script": {
      "sections": [
        {
          "section_name": "trend_hook",
          "dialogue": "...",
          "estimated_duration_seconds": 4,
          "stage_direction": "..."
        }
      ],
      "total_duration_seconds": 28,
      "language_notes": "..."
    },
    "no_match_reason": null
  }
]
```

---

## `style_references.json` Structure

```json
[
  {
    "id": "ref_jakarta_food",
    "niche_tags": ["street food", "jakarta food", "food challenge"],
    "source_description": "Fast-paced Jakarta street food challenge video, ~15 seconds",
    "transcript": "[PLACEHOLDER — fill manually from TikTok]",
    "visual_notes": "[PLACEHOLDER — describe the cuts, text overlays, pacing]"
  },
  {
    "id": "ref_bandung_aesthetic",
    "niche_tags": ["cafe", "bandung", "aesthetic", "soft life"],
    "source_description": "Dreamy Bandung cafe vlog, lo-fi, slow voiceover",
    "transcript": "[PLACEHOLDER — fill manually from TikTok/Reels]",
    "visual_notes": "[PLACEHOLDER]"
  },
  {
    "id": "ref_business_advice",
    "niche_tags": ["entrepreneurship", "business mistakes", "small business"],
    "source_description": "No-nonsense entrepreneur sharing a first-year mistake, warung kopi setting",
    "transcript": "[PLACEHOLDER — fill manually from TikTok]",
    "visual_notes": "[PLACEHOLDER]"
  },
  {
    "id": "ref_finance_talk",
    "niche_tags": ["personal finance", "salary talk", "young professionals"],
    "source_description": "Casual salary/expense breakdown, relatable and slightly comedic",
    "transcript": "[PLACEHOLDER — fill manually from TikTok]",
    "visual_notes": "[PLACEHOLDER]"
  }
]
```

---

## Gemini API Usage Pattern

Based on `script.py` reference code, use `google-genai` SDK:

```python
from google import genai
from google.genai import types

client = genai.Client(api_key=API_KEY)

response = client.models.generate_content(
    model="gemini-2.0-flash",          # free tier, fast
    contents=[prompt],
    config=types.GenerateContentConfig(
        response_mime_type="application/json"   # enforce JSON output
    )
)
result = json.loads(response.text)
```

### Gemini Call Budget (per pipeline run)
| Call | Purpose | Count |
|---|---|---|
| match_call | Trend + template matching for all 4 accounts | 1 |
| draft_call | Script draft per account | 4 |
| critique_call | Critique + refine per account | 4 |
| **Total** | | **9 calls** |

Free tier limit: 15 RPM, 1500 RPD on gemini-2.0-flash → well within limits.

---

## CLI Interface

```bash
python pipeline.py
# Runs full pipeline, saves output/results_<timestamp>.json, prints summary

python pipeline.py --dry-run
# Runs matching only, prints account-trend-template assignments without generating scripts

python pipeline.py --account account_01
# Runs pipeline for a single account only

python pipeline.py --output results.json
# Custom output filename
```

---

## Error Handling & Edge Cases

| Scenario | Handling |
|---|---|
| No trend fits an account (all scores < 0.5) | Output entry with `trend_id: null`, `no_match_reason` explaining the gap |
| Client brief constraint conflicts with trend (e.g. trend involves crypto/trading framing) | Flag in reasoning, skip trend, pick next best |
| Gemini returns malformed JSON | Retry once with explicit "return ONLY raw JSON array" instruction, then fail gracefully |
| Critique pass makes script worse | Compare word count and slang density; if degraded, use draft |
| Rate limit hit | Exponential backoff with 3 retries |
| API key missing | Clear error message: "Set GEMINI_API_KEY env variable or add it to pipeline.py" |

---

## Key Design Decisions

1. **Single-language (Python)** — matches the reference code, keeps dependencies minimal
2. **Gemini 2.0 Flash** — free tier, fast, supports JSON mode which is critical for structured output
3. **9 Gemini calls total** — matching in 1 batch call is efficient and gives comparative reasoning; per-account draft+critique is unavoidable for quality
4. **Hardcoded fallback scoring** — if matching Gemini call fails, the pipeline doesn't die; it uses pre-analyzed scores
5. **style_references.json as static RAG** — avoids scraper complexity, proves multi-modal thinking via stage directions
6. **Critique agent** — the most important quality lever; first drafts from LLMs are always more formal than needed

---

## What Would Change at 50+ Accounts

- Matching call becomes a batch job (group accounts by niche cluster first, then match)
- Style references DB needs at minimum 1 reference per niche cluster, not per account
- Gemini calls: parallelize with `asyncio` + respect rate limits
- Output: write to a database (SQLite or Postgres) instead of single JSON file
- Add a scoring feedback loop: human reviewers rate scripts, scores feed back into prompt tuning
- Template selection becomes a trained classifier, not an LLM call
