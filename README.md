# Content AI Pipeline — SaveKu

A production-grade content generation pipeline that takes structured campaign inputs and produces ready-to-post social media scripts — each matched to the right account, trend, and template with full reasoning transparency and automated quality scoring.

Built for the **CAKAI Software Engineer Assessment**. Fictional client: **SaveKu**, an Indonesian fintech app.

---

## Demo

> **[INSERT LOOM RECORDING LINK HERE]**
> 2–3 minute walkthrough of the pipeline running end-to-end across all 4 accounts.

---

## Quick Start

**Requirements:** Python 3.10+, Node.js 18+, Claude Code CLI installed and logged in.

```bash
# Install dependencies
pip install -r requirements.txt
npm install

# Authenticate (one-time — no API key needed)
claude login

# Smoke test the LLM bridge
python test_api.py

# Run full pipeline
python pipeline.py

# Options
python pipeline.py --dry-run              # matching + template selection only
python pipeline.py --account account_01   # single account for fast iteration
python pipeline.py --output results.json  # custom output filename
```

Output: `output/results_<timestamp>.json` — one entry per account conforming to `output_schema.json`.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Input Layer                                                    │
│  accounts.json · trends.json · templates.json · client_brief   │
│  style_references.json (TikTok transcript corpus)               │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Stage 1+2 — Context Matching & Template Selection              │
│  matcher.py → claude_query.mjs → Claude Agent SDK              │
│  Single LLM call: scores all 4 accounts × 6 trends in one shot │
│  Returns: trend_id, template_id, fit_score, explicit rationale  │
│  Fallback: FALLBACK_MATCHES (pre-analyzed, never fails)         │
└────────────────────────────┬────────────────────────────────────┘
                             │
                      ┌──────┴──────┐
                      │ per account │
                      ▼             ▼
┌────────────────────────────────────────────────────────────────┐
│  Stage 3 — Script Generation (3-pass loop)                     │
│                                                                │
│  Pass 1 — Draft                                                │
│    Style reference injection (TikTok transcript corpus)        │
│    Tone token injection (account slang tokens)                 │
│    Few-shot examples (1 BAD + 1 GOOD)                          │
│    Anti-prompt (forbidden words + formal Indonesian)           │
│    Template structure enforcement                              │
│           │                                                    │
│           ▼                                                    │
│  Pass 2 — Critique                                             │
│    6-criteria review: spoken naturalness, forbidden words,     │
│    CTA quality, slang authenticity, product reveal timing,     │
│    brand voice → revised script if issues found                │
│           │                                                    │
│           ▼                                                    │
│  Pass 3 — Quality Scoring                                      │
│    5-dimension numeric scoring: slang authenticity,            │
│    spoken naturalness, brand compliance, product integration,  │
│    hook strength → overall_score (0–10) + auto_approved flag   │
└────────────────────────────┬───────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Stage 4 — Structured Output                                    │
│  JSON array: script + trend + template + reasoning +            │
│  fit_score + quality_score — saved to output/                   │
└─────────────────────────────────────────────────────────────────┘
```

### LLM Layer — No API Key Required

All LLM calls go through `claude_query.mjs` — a Node.js ESM bridge using the **Claude Agent SDK TypeScript**. Python pipes each prompt via stdin, Node calls the `claude` binary, result returns via stdout. Auth is handled by `claude login` (OAuth). No key in code, no key in environment.

---

## Style Reference Corpus

The highest-leverage quality improvement in this pipeline is **linguistic DNA injection** — instead of describing tone abstractly ("be casual"), the model receives actual transcribed speech from real creators in each niche. It copies cadence, breathing rhythm, filler word frequency, and sentence momentum — not the subject matter.

### Data Collection Methodology

Transcripts were manually extracted from TikTok videos across 4 niche categories, selecting for accounts with the highest comment-to-view ratios (signal of genuine audience resonance, not passive consumption). Each transcript was hand-annotated with visual cut timing to capture the relationship between pacing and editing rhythm.

**5 reference videos per category, 20 transcripts total.**

---

### Category 1 — `jakarta_food_review`

> Street food discovery content. Target: young Jakartans looking for sub-20k meals that feel like finds, not compromises.

Sourced from accounts in the micro-influencer tier (50k–200k followers) to avoid over-polished "creator" voice. The characteristic rhythm: short declarative opener → price drop → reaction → implicit social proof.

| #   | Account             | Content Type          | Followers (approx) |
| --- | ------------------- | --------------------- | ------------------ |
| 1   | `@onebitebigbite`   | Jakarta Food Review   | ~952k              |
| 2   | `@aldo.jusman`      | Hidden gem review     | ~100k              |
| 3   | `@sibungbung`       | Price reveal format   | ~6.2M              |
| 4   | `@kokogemoykuliner` | Spontaneous food vlog | ~117k              |

---

### Category 2 — `bandung_aesthetic_vlog`

> Aesthetic lifestyle content anchored in Bandung. Target: 20s audience who treat weekends as content opportunity and identity expression.

Selected for the characteristic split between visual-heavy narration and introspective monologue. The linguistic signature: slower pacing, rhetorical questions, sensory language, deliberate incomplete sentences.

| #   | Account        | Content Type                 | Followers (approx) |
| --- | -------------- | ---------------------------- | ------------------ |
| 1   | `@mamasu.id`   | Cafe discovery vlog          | ~200k              |
| 2   | `@alfian.afif` | Hidden spot reveal           | ~133k              |
| 3   | `@anthrjonah`  | Weekend itinerary            | ~8k                |
| 4   | `@senafarids`  | Aesthetic corner tour        | ~119k              |
| 5   | `@citrazaraa`  | "Before it's crowded" format | ~153k              |

---

### Category 3 — `business_advice_warung`

> Ground-level business commentary. Target: early-stage entrepreneurs, side-hustlers, and people running small operations.

Selected specifically for the anti-MBA voice — no frameworks, no jargon, no aspirational posturing. The signature: lived experience framing, specific numbers, self-deprecating admissions before the lesson lands.

| #   | Account                   | Content Type                     | Followers (approx) |
| --- | ------------------------- | -------------------------------- | ------------------ |
| 1   | `@iqbalsalmon3`           | First year mistake retrospective | ~50k               |
| 2   | `@miliardermudaindonesia` | Cash flow story                  | ~3.4M              |

---

### Category 4 — `finance_talk`

> Personal finance content in the Indonesian Gen-Z register. Target: first-salary earners, gaji-akhir-bulan crowd, people who follow money content but resist being lectured.

The hardest category to get right — finance content defaults to formal language and moralizing. Selected accounts specifically for their ability to talk about money without sounding like a seminar. Signature: vulnerability-first, specific amounts named, humor as deflection of shame.

| #   | Account                  | Content Type           | Followers (approx) |
| --- | ------------------------ | ---------------------- | ------------------ |
| 1   | `@timothyronaldofficial` | Brutally honest format | ~670k              |
| 2   | `@raymondchins`          | Budget fail story      | ~140k              |

---

### How Style Matching Works

```python
# generator.py — find_style_ref()
# Matches trend's niche_tags against each category's niche_tags
# Returns all videos from the category with the most tag overlap
# All real transcripts (non-placeholder) are injected as numbered references
```

The model receives the transcripts with the instruction to copy **cadence and pacing, not topic** — this is critical. The goal is to extract the phonological and rhythmic signature of authentic speech, not the subject matter.

---

## Prompt Engineering Stack

Each draft generation call layers 6 techniques in sequence:

| Layer | Technique                    | Purpose                                                                                        |
| ----- | ---------------------------- | ---------------------------------------------------------------------------------------------- |
| 1     | **Linguistic DNA injection** | 5 real transcripts → model copies speech rhythm                                                |
| 2     | **Tone token injection**     | Mandatory account-specific slang phrases extracted from profile                                |
| 3     | **Few-shot examples**        | 1 BAD (formal/ad-like) + 1 GOOD (casual/spoken) with explicit failure analysis                 |
| 4     | **Anti-prompt**              | Hard `DO NOT` list: formal connectors, ad openers, forbidden words, breath-test failures       |
| 5     | **Template enforcement**     | JSON structure injected section-by-section with stage direction slots                          |
| 6     | **Product placement rules**  | Explicit timing constraints: product revealed after hook, mentioned once, never the main point |

---

## Quality Control Pipeline

Every script passes through a 3-stage quality control loop before being written to output:

### Stage 1 — Critique Pass

A second LLM call acting as a "brutally honest Indonesian content director" reviews the draft on 6 criteria and returns a revised version with every flagged issue named explicitly:

- Spoken word test (one-breath sentence test)
- Forbidden word scan
- CTA quality (conversational vs. ad-like)
- Slang authenticity (forced vs. native)
- Product reveal timing (too early / too many mentions)
- Brand voice (preachy detection)

### Stage 2 — Numeric Quality Scoring _(newly implemented)_

A third LLM pass produces a structured numeric score that makes quality measurable, not just directional:

| Dimension           | Weight | What It Measures                                             |
| ------------------- | ------ | ------------------------------------------------------------ |
| Spoken naturalness  | 25%    | Sentence length, formal connector absence, filler word usage |
| Brand compliance    | 25%    | Forbidden words, CTA register, non-preachy tone              |
| Slang authenticity  | 20%    | Account-specific tokens used naturally                       |
| Product integration | 15%    | Single mention, post-hook, feels incidental                  |
| Hook strength       | 15%    | First-line scroll-stopping power                             |

**Output per script:**

```json
{
  "quality_score": {
    "scores": {
      "slang_authenticity": 8,
      "spoken_naturalness": 9,
      "brand_compliance": 10,
      "product_integration": 8,
      "hook_strength": 7
    },
    "overall_score": 8.6,
    "score_rationale": "Strong spoken cadence throughout. Hook is specific and relatable. Slang lands naturally at the reveal moment. Minor: product could be revealed 2 seconds later for maximum tension.",
    "auto_approved": true
  }
}
```

Scripts with `auto_approved: false` (score < 7.0) are flagged for manual review before posting.

---

## Edge Cases

| Scenario                               | Handling                                                               |
| -------------------------------------- | ---------------------------------------------------------------------- |
| No trend fits an account (score < 0.5) | `trend_id: null`, `no_match_reason` filled, script skipped             |
| LLM matching call fails                | Falls back to `FALLBACK_MATCHES` — hardcoded, pre-analyzed assignments |
| Script generation fails                | Entry saved with error reason, pipeline continues to next account      |
| Critique finds issues                  | Revised script used; issues listed in terminal output                  |
| Critique finds no issues               | Draft used as-is                                                       |
| Style ref transcript is placeholder    | Draft prompt falls back to account tone description                    |
| Scoring pass fails                     | `quality_score: null`, pipeline continues — non-fatal                  |
| Claude subprocess times out (300s)     | Retried up to 3× with exponential backoff (2s, 4s)                     |

---

## Design Choices

### 1. Python orchestrator + Node.js LLM bridge

Pipeline logic (file loading, matching, output assembly) stays in Python — concise, readable, easy to extend. The LLM layer is a 30-line Node.js bridge using the Claude Agent SDK TypeScript. This separation means Python never touches auth, model versions, or SDK quirks. The bridge is independently swappable.

### 2. Single batch call for matching, per-account calls for scripts

Matching sends all 4 accounts and 6 trends in one prompt — the model can reason about why account A gets trend X _over_ trend Y by comparing them simultaneously. This produces better relative reasoning than 4 isolated calls. Script generation is per-account because prompts are large (style refs + template + brief) and scripts must be account-specific.

### 3. Hardcoded fallback for matching

`FALLBACK_MATCHES` in `matcher.py` has pre-analyzed, manually-reasoned assignments for all 4 accounts. If the matching LLM call fails for any reason, the pipeline degrades gracefully to known-good assignments. It never dies mid-run.

### 4. Static RAG for style references

`style_references.json` is a curated corpus of manually transcribed TikTok excerpts grouped by niche. This gives the model real linguistic DNA rather than abstractly described tone. The format is append-only — adding a new reference is a JSON array append. No scraper, no external API.

### 5. Three-pass quality control (draft → critique → score)

First-pass LLM output skews formal. The critique pass is not optional polish — it's structurally necessary to catch the 6 specific failure modes that make AI content detectable. The scoring pass makes quality measurable and filterable. Together they create a feedback loop where every script is assessed, not just generated.

### 6. Anti-prompt over positive instructions alone

The `DO NOT` list in `build_draft_prompt()` is as important as the style instructions. Telling the model exactly what not to do (no `merupakan`, no `Halo guys`, no sentences longer than one breath) produces more reliable results than positive instructions alone. Both are present in every draft call.

### 7. CLI-first, no UI

A UI adds complexity without adding evaluation signal. The CLI provides `--dry-run` for inspecting matches before committing to LLM calls, `--account` for fast single-account iteration, and timestamped output files so runs never overwrite each other.

---

## What I'd Improve With More Time

**Prompt iteration loop.** The biggest quality lever is the prompt, not the architecture. With more time I'd run the pipeline, read every generated script carefully, identify the most common failure mode across all 4 accounts, fix one thing in `prompts.py`, and repeat. The current few-shot examples and anti-prompt list are a solid first pass but not converged.

**Score-gated regeneration.** Currently the pipeline generates once per account. With the quality scoring pass in place, the natural next step is a regeneration loop: if `auto_approved` is false, regenerate with a revised prompt that incorporates the `score_rationale` as additional constraint. Cap at 2 attempts to avoid infinite loops.

**Structured output enforcement.** Currently the pipeline parses JSON from free-text output, which can fail if the model wraps output in prose. Claude's native structured output (`output_config.format`) would guarantee schema-valid JSON every time, eliminating the `_parse_json()` parsing step and its failure mode entirely.

**Async script generation.** The 4 accounts run sequentially. They're independent — parallel execution with `asyncio` + concurrent subprocesses would cut total runtime from ~4× to ~1× a single generation time.

**Real-time trend ingestion.** `trends.json` is static. A research agent that queries TikTok's trending page, Google Trends Indonesia, and Twitter (X) trending topics would close the loop between external signals and content decisions. Even a lightweight scraper on a cron schedule would make the pipeline genuinely reactive.

**Human review step.** For a real campaign the pipeline should produce candidates, not final posts. A thin terminal prompt — show script, press `a` to approve / `r` to regenerate / `s` to skip — would make this production-ready without requiring a full UI.

---

## How This Changes at 50+ Accounts

**Matching becomes a clustering problem.** Sending 50 accounts and 6 trends in one prompt exceeds context limits and degrades reasoning quality. The fix: cluster accounts by niche first (food, lifestyle, finance, business, etc.), then run one matching call per cluster. The model compares accounts that are actually comparable — 8–12 accounts per call instead of 50.

**Style references need a database.** With 50 accounts spanning more niches, `style_references.json` needs at least one category per niche cluster. A SQLite table replaces the JSON file — query by tag overlap, return top-N transcripts ranked by relevance score.

**Script generation must be parallelized.** 50 accounts × 3 LLM passes = 150 sequential calls is not viable. `asyncio` with a semaphore (e.g. 5 concurrent accounts) respects rate limits without serializing everything. Estimated runtime reduction: 10× vs. sequential.

**Fallback matching must be removed.** `FALLBACK_MATCHES` is hardcoded for 4 specific accounts. At 50 accounts this becomes unmaintainable and wrong. Instead: if the matching call fails, retry with a smaller sub-batch; if retries fail, skip that batch and log it. Never silently produce stale assignments.

**Prompts need per-niche tuning.** A single `build_draft_prompt()` with one few-shot pair doesn't generalize to 50 diverse accounts. Each niche cluster needs its own examples and anti-prompt list — a prompt config file per cluster rather than hardcoded strings in `prompts.py`.

**Quality scoring becomes a classifier, not an LLM call.** At scale, a 150ms LLM scoring call per script is expensive. With enough scored outputs (ground truth from human review), train a lightweight text classifier on the 5 dimensions — logistic regression or a fine-tuned small model. Inference in <5ms per script.

**Output needs a database, not flat files.** 50 accounts × multiple runs per day = thousands of JSON files. SQLite or Postgres with a `runs` table, an `outputs` table, and account/run indexes. Query interface: "show me all scripts for account X from the last 7 days with quality_score >= 7."

**Cost tracking becomes necessary.** At 50 accounts the cost per run starts mattering. Add token usage logging per call (Claude's API returns this), a cost estimate per run, and a rolling 7-day cost view so you can make informed decisions about when to skip the scoring pass for accounts that consistently score well.
