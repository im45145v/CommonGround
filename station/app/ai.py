"""Replaceable AI interface. Default provider talks to a local Ollama-compatible
runtime (Gemma). Any failure/timeout/malformed output yields predictable fallback content,
and every response says which source produced it."""
import json
import random
import urllib.request
from typing import Protocol

from .config import Settings

FALLBACK = {
    "quest": [
        {"title": "Tree Hug Census", "description": "Find the three biggest trees nearby and compare their bark with a friend."},
        {"title": "Sound Map", "description": "Sit quietly for two minutes and list every natural sound you hear."},
        {"title": "Kindness Walk", "description": "Walk the garden and say hello to two people you have not met."},
    ],
    "discussion": [
        {"question": "Is boredom useful? When did being bored last lead you somewhere good?"},
        {"question": "What is something you believed a year ago that you no longer believe?"},
        {"question": "If a campus could teach one thing besides courses, what should it be?"},
    ],
    "radio": [
        {"headline": "Commons Radio", "script": "Good day from the garden station. Put the phone down for ten minutes, "
                                                "take a slow lap, and say hi to someone new. Credits are waiting."},
    ],
}

PROMPTS = {
    "quest": 'Invent one short, safe, free outdoor activity for students. Reply ONLY JSON: {"title": "...", "description": "..."}',
    "discussion": 'Write one thoughtful, non-political discussion question for students. Reply ONLY JSON: {"question": "..."}',
    "radio": 'Write a friendly 2-sentence radio announcement encouraging students to go outside. '
             'Reply ONLY JSON: {"headline": "...", "script": "..."}',
}
REQUIRED = {"quest": ("title", "description"), "discussion": ("question",), "radio": ("headline", "script")}


class Provider(Protocol):
    def complete(self, prompt: str) -> str: ...


class OllamaProvider:
    def __init__(self, s: Settings):
        self.s = s

    def complete(self, prompt: str) -> str:
        body = json.dumps({"model": self.s.ai_model, "prompt": prompt, "stream": False, "format": "json"}).encode()
        req = urllib.request.Request(self.s.ai_url.rstrip("/") + "/api/generate", body, {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.s.ai_timeout) as r:
            return json.loads(r.read())["response"]


def parse(kind: str, text: str):
    """Validate model output; returns a dict of string fields or None."""
    try:
        data = json.loads(text)
        out = {k: str(data[k]).strip()[:400] for k in REQUIRED[kind]}
        return out if all(out.values()) else None
    except Exception:
        return None


def generate(kind: str, provider: Provider | None):
    if provider is not None:
        try:
            out = parse(kind, provider.complete(PROMPTS[kind]))
            if out:
                return out | {"source": "gemma"}
        except Exception:
            pass
    return random.choice(FALLBACK[kind]) | {"source": "fallback"}
