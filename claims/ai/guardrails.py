"""A6: cleaning text before it reaches a model and checking what comes back."""
import json
import re
import unicodedata

CATEGORIES = ("Office visit", "Lab test", "Imaging", "Therapy", "Emergency care",
              "Surgery", "Dental", "Medication", "Other")
FLAGS = ("ok", "review")

MAX_FIELD_CHARS = 200
MAX_NOTE_CHARS = 600
MAX_QUESTION_CHARS = 300  # A9: "Ask about my plan"
MAX_ANSWER_CHARS = 900
NOT_FOUND = "I could not find this in your plan documents."

# Phrases that try to talk to the model instead of describing a bill.
# A9 improvement: the A6 version matched bare words ("disregard", "act as", "ignore the"), which
# rejected ordinary questions such as "Can my insurer disregard my appeal?". Each pattern now needs
# an instruction-like target. The system prompts still tell the models to treat input as data.
_INJECTION = re.compile(
    r"\b(ignore|disregard|forget|override)\b[^.?!]{0,40}\b(instructions?|prompts?|rules|messages?|guidelines)\b|"
    r"system prompt|\byou are now\b|\bact as (if you|an? (ai|assistant|chatbot|model|different|unfiltered))|"
    r"\bpretend (to be|you)\b|jailbreak|developer mode|<\s*/?\s*(system|assistant|user)\s*>|\[/?inst\]|"
    r"reveal (your|the) (system )?(prompt|instructions)",
    re.IGNORECASE,
)


class UnsafeInput(ValueError):
    """Raised when text looks like an attempt to steer the model."""


def clean_text(value, limit=MAX_FIELD_CHARS):
    """Normalise unicode, drop control characters and markup, collapse whitespace, cap length."""
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = "".join(ch for ch in text if ch in "\n\t" or unicodedata.category(ch)[0] != "C")
    text = re.sub(r"<[^>]*>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def check_note(value):
    """Clean a free-text note from the user and refuse prompt-injection attempts."""
    text = clean_text(value, MAX_NOTE_CHARS)
    # Check the raw value too: clean_text strips the <system>-style tags we want to catch.
    if _INJECTION.search(text) or _INJECTION.search(str(value or "")):
        raise UnsafeInput("The note looks like instructions to the AI, not information about the bill.")
    return text


def describe_line_item(item):
    """Turn a BillLineItem into the short fact sheet both models see. Amounts are pre-computed
    here so the model never has to do arithmetic."""
    charged = float(item.charged_amount)
    covered = float(item.estimated_covered_amount)
    owed = float(item.estimated_patient_responsibility)
    pct = round(100 * covered / charged) if charged else 0
    provider = item.bill.provider
    return (
        f"Description: {clean_text(item.description)}\n"
        f"Code: {clean_text(item.procedure_reference) or 'none'}\n"
        f"Provider network: {provider.get_network_status_display()}\n"
        f"Charged: ${charged:,.2f}\n"
        f"Insurance covers: ${covered:,.2f} ({pct}%)\n"
        f"Patient owes: ${owed:,.2f}"
    )


def rule_checks(item):
    """Deterministic checks that never depend on the model."""
    issues = []
    charged = item.charged_amount
    covered = item.estimated_covered_amount
    owed = item.estimated_patient_responsibility
    if covered + owed != charged:
        issues.append("Covered plus patient share does not add up to the charge.")
    if charged and owed / charged >= 0.5:
        issues.append("Patient pays half or more of this charge.")
    if item.bill.provider.network_status == "OUT":
        issues.append("Provider is out of network.")
    return issues


def clean_letter(raw, limit=4000):
    """Tidy an API-written letter: drop markdown markup and control characters, keep paragraphs."""
    text = unicodedata.normalize("NFKC", raw or "")
    text = "".join(ch for ch in text if ch in "\n" or unicodedata.category(ch)[0] != "C")
    text = re.sub(r"^\s*#+\s*", "", text, flags=re.MULTILINE)
    text = text.replace("**", "").replace("__", "")
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text[:limit]


def parse_explanation(raw):
    """Pull the first JSON object out of model text and validate it against our schema.
    Returns a dict, or None when the output is broken."""
    match = re.search(r"\{.*?\}", raw or "", re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    category = str(data.get("category", "")).strip()
    explanation = clean_text(data.get("explanation", ""), 300)
    flag = str(data.get("flag", "")).strip().lower()
    if not explanation:
        return None
    # Snap near-misses ("imaging", "Lab") to a known category instead of rejecting them.
    category = next((c for c in CATEGORIES if c.lower() == category.lower()), None) or next(
        (c for c in CATEGORIES if category and category.lower() in c.lower()), "Other")
    return {"category": category, "explanation": explanation, "flag": flag if flag in FLAGS else "review"}


# ---------------------------------------------------------------- A9: plan questions and grounded answers

_MONEY = re.compile(r"\$\s?(\d[\d,]*(?:\.\d+)?)")
_PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s?%")
_CITATION = re.compile(r"\[(\d+)\]")


def check_question(value):
    """Validate a plan question before any model runs: not empty, not too long, not an injection."""
    raw = str(value or "")
    text = clean_text(raw, 10_000)
    if not text:
        raise UnsafeInput("Type a question about your plan or bill.")
    if len(text) > MAX_QUESTION_CHARS:
        raise UnsafeInput(f"Please keep the question under {MAX_QUESTION_CHARS} characters "
                          f"(yours has {len(text)}).")
    if _INJECTION.search(text) or _INJECTION.search(raw):
        raise UnsafeInput("The question looks like instructions to the AI, not a question about your plan.")
    return text


def _numbers(pattern, text):
    found = set()
    for match in pattern.findall(text or ""):
        try:
            found.add(float(match.replace(",", "")))
        except ValueError:
            pass
    return found


def check_answer(raw, sources):
    """Validate a retrieval-augmented answer against the sources it was given.

    Returns None when the output is unusable, else a dict with the cleaned text, the citations
    that point at real sources, and warnings for anything the patient should double-check:
    missing citations, citations to sources that do not exist, and dollar amounts or
    percentages that appear in no source (a cheap hallucination check)."""
    text = unicodedata.normalize("NFKC", raw or "")
    text = "".join(ch for ch in text if ch in "\n" or unicodedata.category(ch)[0] != "C")
    text = re.sub(r"<[^>]*>", " ", text).replace("**", "").replace("__", "")
    text = re.sub(r"^\s*(#+|answer:)\s*", "", text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(r"\s+", " ", text).strip()[:MAX_ANSWER_CHARS]
    if len(text) < 3:
        return None
    if text.lower().startswith(NOT_FOUND.lower()[:30]):
        return {"text": NOT_FOUND, "citations": [], "grounded": True, "not_found": True, "warnings": []}

    warnings = []
    cited = [int(n) for n in _CITATION.findall(text)]
    invalid = sorted({n for n in cited if not 1 <= n <= len(sources)})
    if invalid:
        text = _CITATION.sub(lambda m: m.group(0) if 1 <= int(m.group(1)) <= len(sources) else "", text)
        text = re.sub(r"\s+([.,;])", r"\1", re.sub(r"\s{2,}", " ", text)).strip()
        warnings.append("Removed a citation to a source that does not exist: "
                        + ", ".join(f"[{n}]" for n in invalid) + ".")
    citations = sorted({n for n in cited if 1 <= n <= len(sources)})
    if not citations:
        warnings.append("This answer does not cite your plan documents. Check the sources below before relying on it.")

    joined = " ".join(sources)
    money = sorted(_numbers(_MONEY, text) - _numbers(_MONEY, joined))
    pct = sorted(_numbers(_PERCENT, text) - _numbers(_PERCENT, joined))
    if money or pct:
        shown = [f"${m:,.2f}".replace(".00", "") for m in money] + [f"{p:g}%" for p in pct]
        warnings.append("Mentions numbers that are not in your plan documents: " + ", ".join(shown) + ".")
    if not text:
        return None
    return {"text": text, "citations": citations, "grounded": bool(citations), "not_found": False,
            "warnings": warnings}
