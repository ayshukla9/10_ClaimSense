"""P1-A6: checks on what goes into and comes out of the language models.

Nothing here imports torch or calls a network, so it is cheap to test.
"""
import json
import re
import unicodedata
from datetime import date
from decimal import Decimal, InvalidOperation

MAX_INPUT_CHARS = 4000
MAX_LINE_ITEMS = 40
MAX_AMOUNT = Decimal("1000000")
MAX_TEXT_FIELD = 200

# Phrases that try to talk to the model instead of describing a bill. We do not
# reject them (a real bill could contain the word "ignore"); we flag them so the
# page can warn, and the prompt already tells the model to treat the text as data.
INJECTION_PATTERNS = [
    r"ignore (all |any )?(previous|prior|above) (instructions|rules)",
    r"disregard (the |all )?(rules|instructions)",
    r"you are now",
    r"system prompt",
    r"reply only with",
]


class GuardrailError(ValueError):
    """Input we refuse to send, or model output we refuse to show."""


def clean_bill_text(raw):
    """Normalise pasted bill text before it reaches a model."""
    text = unicodedata.normalize("NFKC", raw or "")
    # Drop control characters (keep newlines and tabs), which can hide instructions or break tokenizers.
    text = "".join(ch for ch in text if ch in "\n\t" or unicodedata.category(ch)[0] != "C")
    text = "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines())
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        raise GuardrailError("Paste the text of a bill first.")
    if len(text) > MAX_INPUT_CHARS:
        raise GuardrailError(f"That bill is too long ({len(text)} characters; the limit is {MAX_INPUT_CHARS}).")
    if not re.search(r"\d", text):
        raise GuardrailError("That doesn't look like a bill: there are no amounts in it.")
    return text


def injection_warnings(text):
    lowered = text.lower()
    return [pattern for pattern in INJECTION_PATTERNS if re.search(pattern, lowered)]


def extract_json_object(output):
    """Pull the JSON object out of a model reply, tolerating code fences or chatter around it."""
    cleaned = re.sub(r"```(?:json)?", "", output or "")
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        raise GuardrailError("The model did not return any structured data.")
    try:
        value = json.loads(cleaned[start:end + 1])
    except json.JSONDecodeError:
        raise GuardrailError("The model returned broken JSON.")
    if not isinstance(value, dict):
        raise GuardrailError("The model returned the wrong kind of data.")
    return value


def _amount(value):
    if isinstance(value, bool):
        raise GuardrailError("A line item has an invalid amount.")
    try:
        amount = Decimal(str(value).replace("$", "").replace(",", "").strip()).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        raise GuardrailError("A line item has an invalid amount.")
    if not (Decimal("0") < amount < MAX_AMOUNT):
        raise GuardrailError("A line item amount is out of range.")
    return amount


def _short_text(value, field):
    if value is None:
        return ""
    if not isinstance(value, (str, int, float)):
        raise GuardrailError(f"The {field} field has the wrong type.")
    return re.sub(r"\s+", " ", str(value)).strip()[:MAX_TEXT_FIELD]


def validate_parsed_bill(data):
    """Turn raw model JSON into a clean, bounded bill dict, or raise GuardrailError."""
    items = data.get("line_items")
    if not isinstance(items, list) or not items:
        raise GuardrailError("The model found no line items in that text.")
    if len(items) > MAX_LINE_ITEMS:
        raise GuardrailError("The model returned too many line items.")

    bill_date = None
    raw_date = data.get("bill_date")
    if raw_date:
        try:
            bill_date = date.fromisoformat(str(raw_date).strip())
        except ValueError:
            bill_date = None  # an unreadable date is dropped, not fatal

    clean_items = []
    for number, item in enumerate(items, 1):
        if not isinstance(item, dict):
            raise GuardrailError("A line item has the wrong shape.")
        description = _short_text(item.get("description"), "description")
        if not description:
            raise GuardrailError("A line item is missing its description.")
        clean_items.append({
            "line_number": number,
            "description": description,
            "procedure_code": _short_text(item.get("procedure_code"), "procedure code")[:50],
            "charged_amount": _amount(item.get("charged_amount")),
        })
    return {
        "provider": _short_text(data.get("provider"), "provider"),
        "bill_date": bill_date,
        "line_items": clean_items,
        "total_charged": sum((i["charged_amount"] for i in clean_items), Decimal("0")),
    }


def clean_explanation(text, limit=3000):
    """Model prose is shown as escaped text; also trim runaway replies and markdown symbols."""
    text = (text or "").strip()
    if not text:
        raise GuardrailError("The explanation service returned an empty reply.")
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    text = text.replace("**", "")
    return text[:limit]
