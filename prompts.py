"""
prompts.py — All prompt builders for the Content AI pipeline.

Each function takes structured data and returns a prompt string ready to send to Gemini.
JSON mode is enforced at the API call level (response_mime_type="application/json").
"""

import json


def build_match_prompt(accounts: list, trends: list, templates: list) -> str:
    """
    Single prompt to match all accounts to trends + select templates.
    Returns a JSON array with one entry per account.
    """
    accounts_json = json.dumps(accounts, indent=2, ensure_ascii=False)
    trends_json = json.dumps(trends, indent=2, ensure_ascii=False)
    templates_json = json.dumps(
        [{"id": t["id"], "name": t["name"], "best_for": t["best_for"]} for t in templates],
        indent=2,
        ensure_ascii=False,
    )

    return f"""You are a content strategist for an Indonesian AI-driven social media agency.
Your job is to match each account to the most suitable trending topic, then select the best content template.

=== ACCOUNT PROFILES ===
{accounts_json}

=== TRENDING TOPICS ===
{trends_json}

=== CONTENT TEMPLATES (summarized) ===
{templates_json}

=== YOUR TASK ===
For each of the 4 accounts, do the following:

1. TREND SCORING: Score every trend from 0.0 to 1.0 for this account based on:
   - Niche alignment (does the trend topic fit what this account talks about?)
   - Audience match (does the trend audience overlap with the account's audience?)
   - Regional fit (does the trend's region match the account's location/audience?)
   - Format compatibility (does the trend's format suit the account's posting style?)

2. TREND SELECTION: Pick the highest-scoring trend. If the best score is below 0.5, the account has no suitable match.

3. TEMPLATE SELECTION: From the 3 templates, pick the best fit for this account-trend pair.
   Consider: the account's tone, the trend's format, and the template's best_for list.

4. REASONING:
   - trend_match_rationale: 2 sentences explaining WHY this trend fits this account. Be specific — cite actual attributes from both the account profile and the trend.
   - template_selection_rationale: 1 sentence explaining why this template structure fits.
   - alternative_considered: Name the second-best trend option and in 1 sentence why it was not chosen.

5. EDGE CASE: If the best trend score is below 0.5:
   - Set trend_id to null
   - Set template_id to null
   - Set fit_score to the highest score found (even if low)
   - Fill no_match_reason: explain in 1-2 sentences why none of the available trends fit this account

=== OUTPUT FORMAT ===
Return ONLY a raw JSON array. No markdown, no explanation text, no code fences.

[
  {{
    "account_id": "account_01",
    "trend_id": "trend_XX",
    "template_id": "template_XX",
    "fit_score": 0.0,
    "reasoning": {{
      "trend_match_rationale": "...",
      "template_selection_rationale": "...",
      "alternative_considered": "..."
    }},
    "no_match_reason": null
  }}
]
"""


def build_draft_prompt(
    account: dict,
    trend: dict,
    template: dict,
    style_videos: list,
    client_brief: str,
    score_feedback: str = "",
) -> str:
    """
    Full script generation prompt for one account.
    Injects: style references (multiple videos), tone tokens, few-shot examples,
    anti-prompt, template structure.

    style_videos: list of video dicts from a matched style_references.json category.
    """
    # Extract slang tokens from account tone description
    slang_tokens = _extract_slang_tokens(account)
    template_structure = json.dumps(template["structure"], indent=2, ensure_ascii=False)

    # Build style section — inject all available videos that have real transcripts
    real_videos = [v for v in style_videos if "[PLACEHOLDER" not in v.get("transcript", "")]

    if not real_videos:
        style_section = f"""=== STYLE REFERENCE ===
No transcript references available. Base the style entirely on this account's tone and posting style.
Account posting style: {account['posting_style']}
Account tone: {account['tone']}
"""
    else:
        video_blocks = ""
        for i, v in enumerate(real_videos, 1):
            video_blocks += f"""
Reference {i} — {v['niche']}:
Transcript: "{v['transcript']}"
Visual style: {v['visual_cuts']}
"""
        style_section = f"""=== STYLE REFERENCES (linguistic DNA — copy the CADENCE and PACING, NOT the topic) ===
{video_blocks.strip()}

Instruction: Study these transcripts' sentence length, breathing rhythm, filler words, slang frequency, and momentum.
Blend the cadence from across these references. DO NOT copy any of the subject matter.
"""

    return f"""You are a native Indonesian content creator writing a script for {account['handle']} on {account['platform']}.
You are NOT an AI assistant. You are a person who genuinely lives this niche and talks to their phone camera every day.

=== ACCOUNT PERSONA ===
Handle: {account['handle']}
Niche: {account['niche']}
Tone: {account['tone']}
Audience: {account['audience']}
Posting style: {account['posting_style']}

{style_section}
=== CONTENT TEMPLATE TO FOLLOW ===
Template: {template['name']}
Description: {template['description']}
Structure (follow this section by section):
{template_structure}

=== CLIENT BRIEF (SaveKu) ===
{client_brief}

=== TREND TO INCORPORATE ===
Topic: {trend['topic']}
Description: {trend['description']}
Trending format: {trend['trending_format']}
The content must feel like it belongs in this trend — the trend is the vehicle, SaveKu is incidental.

=== SAVEKU PRODUCT DETAILS ===
Product: SaveKu Tabungan Mikro
Key feature: Daily micro-savings goal, as low as Rp 5,000/day, auto-deducted from e-wallet.
How to mention it: Naturally, as something the narrator discovered — NOT as the main point. It should feel like a casual aside, not a product pitch.

=== MANDATORY SLANG TOKENS ===
This account uses these specific phrases. You MUST work at least ONE into the script naturally.
Find the right moment — do NOT force it awkwardly.
Slang tokens: {slang_tokens}

=== FEW-SHOT EXAMPLES ===

BAD script (DO NOT write like this):
"Halo teman-teman! Apakah kalian tahu bahwa menabung sangat penting untuk masa depan finansial kita? Dengan SaveKu, Anda bisa menabung lima ribu rupiah saja setiap harinya untuk meraih tujuan finansial Anda."
Why it fails: Written language, not spoken. Formal connectors. Sounds like a TV commercial. Uses forbidden phrasing. Zero personality. No relatable hook.

GOOD script (write like this):
"Sumpah ya, dulu gue mikir nabung tuh nunggu sisa gaji... Ujung-ujungnya? Ya habis buat ngopi aja sih wkwk. Terus nemu cara gampang banget — literally cuma lima ribu sehari. Gila sih, ternyata gue bisa?"
Why it works: Fragmented spoken sentences. Self-deprecating humor. Ellipses for natural pauses. Relatable scenario first. Product implied, never named directly. Slang feels native.

=== ABSOLUTE DO NOT LIST ===
DO NOT use formal Indonesian connectors: merupakan, adalah, oleh karena itu, dengan demikian, adapun, yakni, yaitu
DO NOT open with: Halo guys, Welcome back, Apa kabar semuanya, Hai semua, Halo teman-teman
DO NOT close with ad language: dapatkan sekarang, segera download, jangan sampai ketinggalan, klik link di bio
DO NOT use forbidden client words: investasi, financial freedom, kebebasan finansial, passive income, grind, hustle, dijamin, crypto, trading, nama kompetitor
DO NOT write sentences longer than one breath — if it takes more than one breath to say, break it into two
DO NOT shame spending habits or frame saving as sacrifice or difficulty
DO NOT make SaveKu the main point of the video — it must feel incidental and naturally discovered
DO NOT use perfect grammar — this is spoken word, people use filler words, incomplete sentences, trailing thoughts

{f'''=== PREVIOUS ATTEMPT FEEDBACK ===
Your last draft did not meet the quality threshold. The reviewer noted:
"{score_feedback}"
Directly address these issues in this attempt. Do not repeat the same mistakes.

''' if score_feedback else ""}=== OUTPUT FORMAT ===
Return ONLY a raw JSON object. No markdown, no explanation, no code fences.
Fill every section from the template structure above. Include stage_direction for each section.

{{
  "sections": [
    {{
      "section_name": "...",
      "dialogue": "...",
      "estimated_duration_seconds": 0,
      "stage_direction": "..."
    }}
  ],
  "total_duration_seconds": 0,
  "language_notes": "Brief note on slang used, language mix (Bahasa/English ratio), tone calibration for this specific account."
}}
"""


def build_critique_prompt(account: dict, draft_script: dict, client_brief_forbidden: list) -> str:
    """
    Critique pass prompt. Reviews the draft for quality issues and returns a revised version.
    """
    slang_tokens = _extract_slang_tokens(account)
    draft_json = json.dumps(draft_script, indent=2, ensure_ascii=False)
    forbidden_str = ", ".join(client_brief_forbidden)

    return f"""You are an expert Indonesian Gen-Z/millennial TikTok and Reels content director.
You have spent 5 years reviewing scripts that fail because they sound written, not spoken.
You are brutally honest but constructive.

You are reviewing a script for {account['handle']} ({account['niche']}).
Account tone: {account['tone']}
Account audience: {account['audience']}

=== DRAFT SCRIPT TO REVIEW ===
{draft_json}

=== YOUR EVALUATION CRITERIA ===

1. SPOKEN WORD TEST
   Read every line of dialogue out loud mentally. Flag any line that sounds like it was written for a reader, not spoken to a phone camera.
   Signs of failure: long compound sentences, formal grammar, no pauses, no fillers, no personality.

2. FORBIDDEN WORDS CHECK
   Scan for these words — flag immediately if found: {forbidden_str}
   Also flag: merupakan, adalah, oleh karena itu, dengan demikian, adapun

3. CTA QUALITY
   Does the ending feel like a real person finishing a story with a friend?
   Or does it sound like an ad? Flag if it sounds like an ad.
   Good CTA ends with a question, a soft nudge, or social proof — never a command.

4. SLANG AUTHENTICITY
   Are the account's slang tokens ({slang_tokens}) used naturally?
   Flag if they feel forced, awkward, or missing entirely.

5. PRODUCT REVEAL TIMING
   Is SaveKu mentioned too early (before the audience is emotionally hooked)?
   Is it mentioned too many times (more than once is usually too much)?
   Flag if the product feels like the main point instead of a natural discovery.

6. BRAND VOICE
   Never preachy. Never condescending about spending.
   Flag if any line lectures the audience about their habits.

=== OUTPUT FORMAT ===
Return ONLY a raw JSON object. No markdown, no explanation outside the JSON.

{{
  "issues_found": [
    "Issue description 1 — cite the specific line and why it fails",
    "Issue description 2"
  ],
  "revised_script": {{
    "sections": [
      {{
        "section_name": "...",
        "dialogue": "...",
        "estimated_duration_seconds": 0,
        "stage_direction": "..."
      }}
    ],
    "total_duration_seconds": 0,
    "language_notes": "..."
  }}
}}

IMPORTANT: If no issues are found, return an empty issues_found array and copy the original script unchanged into revised_script.
If issues ARE found, fix every flagged line in the revised_script. The revised version should fix all issues while keeping the good parts.
"""


# ─── Internal helpers ────────────────────────────────────────────────────────

def _extract_slang_tokens(account: dict) -> str:
    """
    Extract explicit slang phrases mentioned in the account's tone description.
    Falls back to the tone description itself if no quoted phrases found.
    """
    import re
    tone = account.get("tone", "")
    # Find anything in single quotes like 'gila sih' or 'ini real'
    quoted = re.findall(r"'([^']+)'", tone)
    if quoted:
        return str(quoted)
    # Fallback: return the raw tone as style guidance
    return f"[tone reference: {tone}]"


def build_scoring_prompt(account: dict, script: dict, client_brief_forbidden: list) -> str:
    """
    Automated quality scoring pass (Pass 3). Produces a numeric score across 5 dimensions.
    Returns a quality_score dict with per-dimension scores, overall_score, rationale, and auto_approved flag.
    """
    slang_tokens = _extract_slang_tokens(account)
    script_json = json.dumps(script, indent=2, ensure_ascii=False)
    forbidden_str = ", ".join(client_brief_forbidden)

    return f"""You are a quality control analyst for an Indonesian social media agency.
You are scoring a final script for {account['handle']} ({account['niche']}) on {account['platform']}.
Score each dimension from 0 to 10. Be strict and precise. A 10 is rare — reserve it for genuinely exceptional execution.

=== SCRIPT TO SCORE ===
{script_json}

=== SCORING DIMENSIONS ===

1. SLANG_AUTHENTICITY (0-10)
   Required slang tokens for this account: {slang_tokens}
   10 = at least one slang token used at a natural, contextually correct moment — feels native
   5  = slang present but slightly forced or inserted awkwardly
   0  = slang missing entirely, or account's language register is wrong throughout
   Also consider: is the overall vocabulary consistent with how {account['audience']} actually talk?

2. SPOKEN_NATURALNESS (0-10)
   10 = every single line passes the one-breath test, fragments and fillers feel native, no written-language patterns
   5  = most lines work but 1-2 sentences feel composed rather than spoken
   0  = reads like a blog post, essay, or press release
   Check specifically: absence of formal connectors (merupakan, adalah, oleh karena itu, dengan demikian),
   sentence fragments used correctly, pauses implied with ellipses or short sentences.

3. BRAND_COMPLIANCE (0-10)
   Forbidden words: {forbidden_str}
   Also forbidden: merupakan, adalah, oleh karena itu, dengan demikian, adapun
   10 = zero forbidden words, CTA is soft/conversational (question, social proof, or soft nudge), no preachy lines about spending
   5  = minor CTA issue or one slightly lecturing line
   0  = forbidden word present, or CTA is a direct command ("download sekarang", "klik link di bio")

4. PRODUCT_INTEGRATION (0-10)
   10 = SaveKu/product mentioned exactly once, after the emotional hook is established, as a casual personal discovery
   7  = product mentioned once but slightly too early, or slightly too prominent
   4  = product mentioned twice, or feels like the main point of the video
   0  = product is the opening topic, mentioned 3+ times, or script is clearly an ad

5. HOOK_STRENGTH (0-10)
   10 = opening line would stop a mid-scroll — specific, creates immediate tension, curiosity, or recognition
   6  = decent hook but generic, slow, or takes >3 seconds to establish stakes
   0  = opens with a greeting, or a generic statement ("Jadi gini...", "Halo guys", "Oke jadi...")

=== OUTPUT FORMAT ===
Return ONLY a raw JSON object. No markdown, no explanation outside JSON.

{{
  "scores": {{
    "slang_authenticity": 0,
    "spoken_naturalness": 0,
    "brand_compliance": 0,
    "product_integration": 0,
    "hook_strength": 0
  }},
  "overall_score": 0.0,
  "score_rationale": "2-3 sentences: what is working well, and what specifically is dragging the score down.",
  "auto_approved": false
}}

Calculation rules:
- overall_score = (slang_authenticity × 0.20) + (spoken_naturalness × 0.25) + (brand_compliance × 0.25) + (product_integration × 0.15) + (hook_strength × 0.15)
- Round overall_score to 1 decimal place
- auto_approved = true if overall_score >= 7.0, false otherwise
"""


# ─── Constants ────────────────────────────────────────────────────────────────

# Forbidden words list extracted from client_brief.md for use in critique prompt
FORBIDDEN_WORDS = [
    "investasi",
    "financial freedom",
    "kebebasan finansial",
    "passive income",
    "grind",
    "hustle",
    "dijamin",
    "crypto",
    "trading",
]
