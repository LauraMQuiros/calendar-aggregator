"""LLM-based event extraction from cleaned text.

Supports:
- Local models via Ollama (OLLAMA_MODEL=llama3.2)
- Local models via Hugging Face transformers (USE_TRANSFORMERS=1, TRANSFORMERS_MODEL=...)
- Cloud APIs: Anthropic, OpenAI (fallback if no local model)
"""

import json
import logging
import os
import re
from typing import Any
import nltk
from nltk.corpus import stopwords
from openai import OpenAI

logger = logging.getLogger(__name__)

# Local model config (checked first)
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")  # default llama3.2 - run: ollama pull llama3.2
OLLAMA_TIMEOUT = float(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "120"))  # fail after N seconds instead of hanging
USE_TRANSFORMERS = os.environ.get("USE_TRANSFORMERS", "").lower() in ("1", "true", "yes")
TRANSFORMERS_MODEL = os.environ.get("TRANSFORMERS_MODEL", "Qwen/Qwen2-1.5B-Instruct")

# Cloud APIs (fallback)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")


EXTRACTION_PROMPT = """Extract all events from the following text. Return a JSON array of objects. Each object must have these fields:
- title (string, required)
- date (string, required - ISO date YYYY-MM-DD if possible, otherwise best guess)
- time (string, optional - e.g. "14:00" or "2:00 PM")
- location (string, optional)
- description (string, optional)
- source_url (string, required - use the URL provided below)

If the text is not in English, translate title, description, and location to English. Set "original_language" on each event if you detected a non-English source.

If no events are found, return an empty array [].

Text to extract from:
---
{text}
---

Source URL (use for source_url on each event): {source_url}

Return ONLY valid JSON, no other text. Use only ASCII in strings (e.g. write "a" for å, "o" for ö) to avoid encoding issues."""


def _get_stopwords() -> set[str]:
    """NLTK stopwords (EN + SV), excluding words that could be dates/titles e.g. May."""
    try:
        nltk.download("stopwords", quiet=True)
    except Exception as e:
        logger.warning("NLTK stopwords not available (%s), using minimal set", e)
        return {"the", "a", "an", "and", "or", "is", "are", "was", "were", "in", "on", "at", "to", "for", "of"}
    en = set(stopwords.words("english"))
    try:
        sv = set(stopwords.words("swedish"))
    except OSError:
        sv = set()
    # Don't remove month names / title-like words
    exclude = {"may", "march", "april", "june", "july", "august", "september", "october", "november", "december", "january", "february"}
    return (en | sv) - exclude


_STOPWORDS_CACHE: set[str] | None = None


def _normalize_text_for_prompt(text: str) -> str:
    """Collapse whitespace and remove NLTK stopwords to shorten the prompt (stay under token limit)."""
    global _STOPWORDS_CACHE
    if _STOPWORDS_CACHE is None:
        _STOPWORDS_CACHE = _get_stopwords()
    text = re.sub(r"\s+", " ", text).strip()
    # O(n) set-lookup instead of a huge regex alternation
    words = text.split(" ")
    filtered = [w for w in words if w.lower() not in _STOPWORDS_CACHE]
    return " ".join(filtered)


# Event-section markers to keep only event-relevant text (avoids sending nav/FAQ to LLM)
_EVENT_SECTION = re.compile(
    r"(?:^|\n)\s*(?:#+\s*)?(?:Kommande evenemang|Upcoming events|Events?|Calendar|Program(?:me)?|Event calendar|Agenda)\s*[:\s]",
    re.IGNORECASE | re.MULTILINE,
)
# Only match clear section *headers* — not inline nav links like "Läs mer" / "Se alla"
# which appear inside the event block itself and falsely truncate it
_NON_EVENT_SECTION = re.compile(
    r"(?:\n|^)\s*(?:#+\s*)?(?:FAQ|Contact|About us|Om oss|Kontakt|Media|Sponsors|Donera)\s*[:\s]",
    re.IGNORECASE | re.MULTILINE,
)
OLLAMA_MAX_TEXT_CHARS = int(os.environ.get("OLLAMA_MAX_TEXT_CHARS", "2500"))


def _filter_to_event_section(text: str, max_chars: int) -> str:
    """Keep only the event listing block; drop nav, footer, FAQ. Caps at max_chars."""
    if len(text) <= max_chars:
        logger.debug("_filter_to_event_section: text fits in max_chars (%d <= %d), passing through", len(text), max_chars)
        return text
    m = _EVENT_SECTION.search(text)
    if m:
        start = m.start()
        rest = text[start:]
        end_m = _NON_EVENT_SECTION.search(rest)
        if end_m:
            rest = rest[: end_m.start()]
        # Only stop at "Load more" / "bottom of page" — not "Se alla"/"Läs mer" which appear
        # as inline links on every event card and would cut the block after the first event
        for stop in ("Läs in fler", "Load more", "bottom of page"):
            i = rest.find(stop)
            if i != -1:
                rest = rest[:i]
        block = rest.strip()
        logger.debug(
            "_filter_to_event_section: found event section at char %d, block length %d (max %d)",
            start, len(block), max_chars,
        )
        if len(block) < 50:
            logger.warning(
                "_filter_to_event_section: event block suspiciously short (%d chars) — "
                "check that _NON_EVENT_SECTION or stop phrases aren't cutting it too early. "
                "Falling back to raw text[:max_chars].",
                len(block),
            )
            return text[:max_chars].rsplit("\n", 1)[0] + "\n"
        return block[:max_chars].rsplit("\n", 1)[0] + "\n" if len(block) > max_chars else block
    logger.debug("_filter_to_event_section: no event section header found, truncating to %d chars", max_chars)
    return text[:max_chars].rsplit("\n", 1)[0] + "\n"


def extract_events(text: str, source_url: str, source_language: str | None = None) -> list[dict[str, Any]]:
    """
    Extract event objects from cleaned text using an LLM.

    Args:
        text: Cleaned plain text from the webpage.
        source_url: URL of the source page (for source_url on each event).
        source_language: Optional hint for source language (e.g. "sv", "es").

    Returns:
        List of event dicts: [{title, date, time, location, description, source_url}, ...]
    """
    if not text or len(text.strip()) < 20:
        return []

    text = _normalize_text_for_prompt(text)
    max_chars = OLLAMA_MAX_TEXT_CHARS if OLLAMA_MODEL else 50000
    text = _filter_to_event_section(text, max_chars)
    prompt = EXTRACTION_PROMPT.format(text=text, source_url=source_url)

    if source_language:
        prompt += f"\n\nNote: The source text appears to be in {source_language}. Translate event details to English."

    # Prefer local models, then cloud APIs
    if OLLAMA_MODEL:
        return _extract_ollama(prompt)
    if USE_TRANSFORMERS:
        return _extract_transformers(prompt)
    if ANTHROPIC_API_KEY:
        return _extract_anthropic(prompt)
    if OPENAI_API_KEY:
        return _extract_openai(prompt)
    raise ValueError(
        "Configure a model: OLLAMA_MODEL=llama3.2 (local), USE_TRANSFORMERS=1 (local), "
        "or OPENAI_API_KEY / ANTHROPIC_API_KEY (cloud)"
    )


def _extract_ollama(prompt: str) -> list[dict[str, Any]]:
    """Use local Ollama. Install: https://ollama.com. Then: ollama pull llama3.2"""
    try:
        client = OpenAI(
            base_url="http://localhost:11434/v1",
            api_key="ollama",
            timeout=OLLAMA_TIMEOUT,
        )
        response = client.chat.completions.create(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,  # events are short; 512 is enough and much faster than 2048
            temperature=0,  # deterministic, slightly faster
        )
        text = response.choices[0].message.content or ""
        return _parse_json_events(text)
    except ImportError:
        raise ValueError("Install openai: pip install openai")
    except Exception as e:
        logger.exception("Ollama extraction failed (is ollama running? ollama serve): %s", e)
        raise


_transformers_model = None
_transformers_tokenizer = None


def _extract_transformers(prompt: str) -> list[dict[str, Any]]:
    """Use Hugging Face transformers. Model is downloaded on first run (~1-3GB)."""
    global _transformers_model, _transformers_tokenizer
    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch

        model_name = TRANSFORMERS_MODEL
        if _transformers_model is None:
            logger.info("Loading model %s (first run downloads ~1-3GB)...", model_name)
            _transformers_tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
            _transformers_model = AutoModelForCausalLM.from_pretrained(
                model_name,
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                device_map="auto" if torch.cuda.is_available() else None,
                trust_remote_code=True,
            )
            if not torch.cuda.is_available():
                _transformers_model = _transformers_model.to("cpu")
        model, tokenizer = _transformers_model, _transformers_tokenizer

        messages = [{"role": "user", "content": prompt}]
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        inputs = tokenizer(text, return_tensors="pt").to(model.device)
        outputs = model.generate(
            **inputs,
            max_new_tokens=2048,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
        response = tokenizer.decode(outputs[0][inputs["input_ids"].shape[1] :], skip_special_tokens=True)
        return _parse_json_events(response)
    except ImportError as e:
        raise ValueError("Install: pip install transformers torch accelerate") from e
    except Exception as e:
        logger.exception("Transformers extraction failed: %s", e)
        raise


def _extract_anthropic(prompt: str) -> list[dict[str, Any]]:
    try:
        import anthropic

        client = anthropic.Anthropic()
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text
        return _parse_json_events(text)
    except ImportError:
        raise ValueError("Install anthropic: pip install anthropic")
    except Exception as e:
        logger.exception("Anthropic extraction failed: %s", e)
        raise


def _extract_openai(prompt: str) -> list[dict[str, Any]]:
    try:
        from openai import OpenAI

        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096,
        )
        text = response.choices[0].message.content or ""
        return _parse_json_events(text)
    except ImportError:
        raise ValueError("Install openai: pip install openai")
    except Exception as e:
        logger.exception("OpenAI extraction failed: %s", e)
        raise


def _fix_invalid_unicode_escapes(s: str) -> str:
    """Repair invalid \\uXXXX escapes that some LLMs produce."""
    import re

    def repl(m: "re.Match[str]") -> str:
        hex_part = m.group(1)
        hex_clean = "".join(c for c in hex_part if c in "0123456789abcdefABCDEF")[:4]
        if len(hex_clean) == 4:
            try:
                return chr(int(hex_clean, 16))
            except (ValueError, OverflowError):
                return "\ufffd"
        if len(hex_clean) >= 1:
            try:
                return chr(int(hex_clean.ljust(4, "0")[:4], 16))
            except (ValueError, OverflowError):
                pass
        return "\ufffd"

    # Match \u + any run of hex (valid 4, or invalid <4, or invalid with non-hex, or overlong 5+)
    # Stop at: another \u, non-hex, end of string
    return re.sub(r"\\u([0-9a-fA-F]*?)(?=\\u|[^0-9a-fA-F]|$)", repl, s)


def _parse_json_events(raw: str) -> list[dict[str, Any]]:
    raw = raw.strip()
    # Handle markdown code blocks
    if raw.startswith("```"):
        lines = raw.split("\n")
        start = 1 if lines[0].startswith("```") else 0
        end = len(lines)
        for i, line in enumerate(lines):
            if i > 0 and line.strip() == "```":
                end = i
                break
        raw = "\n".join(lines[start:end])

    # Pre-decode ALL \u escapes before json.loads (avoids "Invalid \uXXXX" from Ollama)
    raw = _fix_invalid_unicode_escapes(raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        try:
            from json_repair import repair_json

            data = json.loads(repair_json(raw))
        except (ImportError, json.JSONDecodeError):
            logger.warning("Failed to parse LLM response as JSON: %s", e)
            return []

    if not isinstance(data, list):
        return []
    events = []
    for item in data:
        if isinstance(item, dict) and item.get("title"):
            e = {
                "title": str(item.get("title", "")),
                "date": str(item.get("date", "")),
                "time": str(item.get("time", "")) if item.get("time") else None,
                "location": str(item.get("location", "")) if item.get("location") else None,
                "description": str(item.get("description", "")) if item.get("description") else None,
                "source_url": str(item.get("source_url", "")),
            }
            if item.get("original_language"):
                e["original_language"] = str(item["original_language"])
            events.append(e)
    return events