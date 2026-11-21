"""One function, many models. Swap the model with LLM_PROVIDER / LLM_MODEL env vars.

Providers:
  gemini     - Google AI Studio free tier   (GEMINI_API_KEY)
  groq       - Groq free tier, Llama etc.   (GROQ_API_KEY)
  openai     - any OpenAI-compatible API     (OPENAI_API_KEY, OPENAI_BASE_URL optional)
  anthropic  - Claude API                    (ANTHROPIC_API_KEY)
  claude_cli - local `claude -p` (Claude Code CLI, no key needed if logged in)
  none       - no LLM; rules-only scoring
"""
import json
import os
import re
import subprocess
import time

import requests

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
except ImportError:
    pass

KEY_ENV = {  # order = auto-selection priority
    "groq": "GROQ_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}

DEFAULT_MODELS = {
    "gemini": "gemini-3.5-flash",
    "groq": "openai/gpt-oss-120b",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-sonnet-5-5",
    "claude_cli": "",
}


def available_providers() -> list:
    """Providers whose API key is present in the environment."""
    return [p for p, k in KEY_ENV.items() if os.getenv(k)]


def provider() -> str:
    """LLM_PROVIDER if set, otherwise the first provider with a configured key, otherwise 'none'."""
    p = os.getenv("LLM_PROVIDER", "").strip().lower()
    if p:
        return p
    avail = available_providers()
    return avail[0] if avail else "none"


def _post(url: str, headers: dict, payload: dict, timeout: int, retries: int = 3):
    """POST with exponential backoff on rate limits and transient server errors."""
    for attempt in range(retries + 1):
        r = requests.post(url, headers=headers, json=payload, timeout=timeout)
        if r.status_code in (429, 500, 502, 503, 504) and attempt < retries:
            time.sleep(2 ** (attempt + 1))
            continue
        if not r.ok:
            raise RuntimeError(f"{r.status_code} from {url.split('?')[0]}: {r.text[:300]}")
        return r


def complete(prompt: str, provider_name: str = None, model: str = None, api_key: str = None,
             timeout: int = 180) -> str:
    p = (provider_name or provider()).lower()
    key = api_key or os.getenv(KEY_ENV.get(p, ""), "")
    model = model or os.getenv("LLM_MODEL", "").strip() or DEFAULT_MODELS.get(p, "")

    if p == "gemini":
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        r = _post(url, {"x-goog-api-key": key},
                  {"contents": [{"parts": [{"text": prompt}]}],
                   "generationConfig": {"temperature": 0.2}}, timeout)
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]

    if p in ("groq", "openai"):
        base = ("https://api.groq.com/openai/v1" if p == "groq"
                else os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"))
        r = _post(f"{base}/chat/completions", {"Authorization": f"Bearer {key}"},
                  {"model": model, "temperature": 0.2,
                   "messages": [{"role": "user", "content": prompt}]}, timeout)
        return r.json()["choices"][0]["message"]["content"]

    if p == "anthropic":
        r = _post("https://api.anthropic.com/v1/messages",
                  {"x-api-key": key, "anthropic-version": "2023-06-01"},
                  {"model": model, "max_tokens": 1500,
                   "messages": [{"role": "user", "content": prompt}]}, timeout)
        return r.json()["content"][0]["text"]

    if p == "claude_cli":
        cmd = ["claude", "-p", "--output-format", "text"] + (["--model", model] if model else [])
        out = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                             encoding="utf-8", timeout=timeout)
        if out.returncode != 0:
            raise RuntimeError(out.stderr[:500])
        return out.stdout

    raise ValueError(f"No LLM provider configured ({p})")


def extract_json(text: str):
    """Models often wrap JSON in prose or ``` fences; pull out the first JSON object/array."""
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        text = m.group(1)
    start = min([i for i in (text.find("{"), text.find("[")) if i != -1], default=-1)
    if start == -1:
        raise ValueError("no JSON in model output")
    return json.loads(text[start:text.rfind("}" if text[start] == "{" else "]") + 1])
