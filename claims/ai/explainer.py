"""P1-A6 feature 2: plain-English bill explanations from a large model on Groq's API.

Groq hosts open models (default gpt-oss-120b) behind an OpenAI-compatible chat API
with a free tier. Only bill facts are sent: provider, network status, plan rules and
line items. Patient names, netids, emails and bill numbers never leave the server.
"""
import requests
from django.conf import settings

from .guardrails import GuardrailError, clean_explanation

API_URL = "https://api.groq.com/openai/v1/chat/completions"

INSTRUCTIONS = """You explain US medical bills to patients for the ClaimSense app.
Using only the facts provided, write a short plain-English explanation (under 180 words):
1. What each charge is, in everyday words.
2. Why the plan covers what it does (network status, coinsurance), using the numbers given.
3. One or two practical next steps, e.g. what to check or ask the provider or insurer.
Do not invent charges, prices or plan rules. We do not know how much of the deductible or
out-of-pocket maximum has already been met this year, so never assume either way; say it is unknown.
Do not give medical or legal advice. If something is missing, say so. Plain text only: no headings,
tables or markdown."""


class AIServiceError(RuntimeError):
    """The explanation API is not configured, unreachable, or returned nothing usable."""


def _money(value):
    return f"${float(value):,.2f}" if value is not None else "unknown"


def describe_bill(bill):
    """Facts about a saved Bill, without anything that identifies the patient."""
    plan = bill.insurance_plan
    lines = [
        f"Provider: {bill.provider.name} ({bill.provider.get_network_status_display()})",
        f"Bill date: {bill.bill_date.isoformat()}",
        f"Plan type: {plan.plan_type}; deductible {_money(plan.deductible)}; coinsurance {plan.coinsurance_pct}%; "
        f"out-of-pocket max {_money(plan.out_of_pocket_max)}",
        "Line items (charged / estimated covered by plan / estimated patient owes):",
    ]
    for item in bill.line_items.all():
        code = f" [{item.procedure_reference}]" if item.procedure_reference else ""
        lines.append(
            f"- {item.description}{code}: {_money(item.charged_amount)} / "
            f"{_money(item.estimated_covered_amount)} / {_money(item.estimated_patient_responsibility)}"
        )
    return "\n".join(lines)


def describe_parsed(parsed):
    """Facts about a bill the local model just parsed (no coverage estimates exist yet)."""
    lines = [
        f"Provider: {parsed['provider'] or 'unknown'} (network status unknown)",
        f"Bill date: {parsed['bill_date'].isoformat() if parsed['bill_date'] else 'unknown'}",
        "Plan details: not provided",
        "Line items (charged amounts only):",
    ]
    for item in parsed["line_items"]:
        code = f" [{item['procedure_code']}]" if item["procedure_code"] else ""
        lines.append(f"- {item['description']}{code}: {_money(item['charged_amount'])}")
    lines.append(f"Total charged: {_money(parsed['total_charged'])}")
    return "\n".join(lines)


def explain(facts):
    """Send bill facts to the explanation model and return cleaned plain text."""
    if not settings.GROQ_API_KEY:
        raise AIServiceError("Bill explanations aren't set up on this server (no Groq API key).")
    try:
        response = requests.post(
            API_URL,
            headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
            json={
                "model": settings.EXPLAIN_MODEL,
                "messages": [{"role": "system", "content": INSTRUCTIONS}, {"role": "user", "content": facts}],
                "temperature": 0.2,
                # gpt-oss models reason before answering; reasoning tokens count against this limit.
                "max_completion_tokens": 1500,
                **({"include_reasoning": False, "reasoning_effort": "low"} if "gpt-oss" in settings.EXPLAIN_MODEL else {}),
            },
            timeout=settings.EXPLAIN_TIMEOUT_SECONDS,
        )
    except requests.Timeout:
        raise AIServiceError("The explanation service took too long. Try again in a moment.")
    except requests.RequestException:
        raise AIServiceError("Could not reach the explanation service.")
    if response.status_code == 429:
        raise AIServiceError("The explanation service is busy (rate limit). Try again in a minute.")
    if not response.ok:
        raise AIServiceError(f"The explanation service returned an error (HTTP {response.status_code}).")
    try:
        text = response.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError):
        raise AIServiceError("The explanation service returned an unexpected reply.")
    try:
        return clean_explanation(text)
    except GuardrailError as exc:
        raise AIServiceError(str(exc))
