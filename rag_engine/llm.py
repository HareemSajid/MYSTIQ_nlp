"""Gemini REST client (no SDK dependency). Returns (text, latency_ms, error). Never raises."""
import time
import requests
from django.conf import settings


def gemini_available():
    return bool(settings.MYSTIQ["GEMINI_API_KEY"])


def generate(system: str, prompt: str, max_tokens=350, temperature=0.35):
    cfg = settings.MYSTIQ
    if not cfg["GEMINI_API_KEY"]:
        return None, 0, "no_api_key"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{cfg['GEMINI_MODEL']}:generateContent"
    body = {"system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens}}
    t0 = time.perf_counter()
    try:
        r = requests.post(url, json=body, headers={"x-goog-api-key": cfg["GEMINI_API_KEY"]}, timeout=cfg["LLM_TIMEOUT"])
        ms = int((time.perf_counter() - t0) * 1000)
        if r.status_code != 200:
            return None, ms, f"http_{r.status_code}"
        data = r.json()
        parts = data["candidates"][0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts).strip()
        return (text or None), ms, None if text else "empty"
    except Exception as exc:
        return None, int((time.perf_counter() - t0) * 1000), type(exc).__name__
