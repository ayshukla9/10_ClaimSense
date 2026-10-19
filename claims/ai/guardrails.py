"""A6: cleaning text before it reaches a model and checking what comes back."""
import json
import re
import unicodedata

CATEGORIES = ("Office visit", "Lab test", "Imaging", "Therapy", "Emergency care",
              "Surgery", "Dental", "Medication", "Other")
FLAGS = ("ok", "review")

MAX_FIELD_CHARS = 200
MAX_NOTE_CHARS = 600

# Phrases that try to talk to the model instead of describing a bill.
_INJECTION = re.compile(
    r"ignore (all|any|the|previous|prior)|disregard|system prompt|you are now|act as|"
    r"jailbreak|developer mode|<\s*/?\s*(system|assistant|user)\s*>|\[/?inst\]|"
    r"reveal (your|the) (prompt|instructions)",
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
