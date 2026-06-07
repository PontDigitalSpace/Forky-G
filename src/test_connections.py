#!/usr/bin/env python3
"""
Test all 4 API connections. Run from /src:
  python3 test_connections.py
"""
import os
import sys
import requests
from pathlib import Path

# Load .env
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

results = {}

# 1. Anthropic
try:
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        },
        json={"model": "claude-haiku-4-5-20251001", "max_tokens": 10,
              "messages": [{"role": "user", "content": "ping"}]}
    )
    r.raise_for_status()
    results["Anthropic"] = "✅ OK"
except Exception as e:
    results["Anthropic"] = f"❌ {e}"

# 2. Higgsfield
try:
    r = requests.get(
        "https://api.higgsfield.ai/v1/models",
        headers={"Authorization": f"Bearer {os.environ['HIGGSFIELD_API_KEY']}"}
    )
    r.raise_for_status()
    results["Higgsfield"] = "✅ OK"
except Exception as e:
    results["Higgsfield"] = f"❌ {e}"

# 3. OpenAI TTS
try:
    r = requests.post(
        "https://api.openai.com/v1/audio/speech",
        headers={
            "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
            "Content-Type": "application/json"
        },
        json={"model": "tts-1", "input": "test", "voice": "nova", "response_format": "mp3"}
    )
    r.raise_for_status()
    results["OpenAI TTS"] = "✅ OK"
except Exception as e:
    results["OpenAI TTS"] = f"❌ {e}"

# 4. Descript
try:
    key = os.environ["DESCRIPT_API_KEY"]
    r = requests.get(
        "https://api.descript.com/v2/projects",
        headers={"Authorization": f"Bearer {key}"}
    )
    r.raise_for_status()
    results["Descript"] = "✅ OK"
except Exception as e:
    results["Descript"] = f"❌ {e}"

print("\n── API Connection Test ──────────────────")
for name, status in results.items():
    print(f"  {name:15} {status}")
print("─────────────────────────────────────────\n")

if any("❌" in v for v in results.values()):
    sys.exit(1)
