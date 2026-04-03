"""
test_api.py — Smoke test for Claude Agent SDK (claude_query.mjs).
Run: python test_api.py
"""

import os
import subprocess
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
prompt = 'Reply with only this JSON object, no other text: {"status": "ok", "model": "claude"}'

print("Testing Claude Agent SDK via claude_query.mjs...")

env = os.environ.copy()

proc = subprocess.run(
    ["node", str(BASE_DIR / "claude_query.mjs")],
    input=prompt,
    capture_output=True,
    text=True,
    timeout=120,
    env=env,
)

print(f"Exit code: {proc.returncode}")
if proc.stdout:
    print(f"Response: {proc.stdout}")
if proc.stderr:
    print(f"Stderr: {proc.stderr}")

if proc.returncode == 0:
    print("\nAgent SDK is working.")
else:
    print("\nAgent SDK failed.")
