"""
P1-A4 Part 2: external API (no key needed).

Searches HCPCS procedure codes on the NLM Clinical Tables API and shows
them next to our own line items for the same keyword. Nothing that comes
back gets saved.
"""
import requests
from django.db.models import Avg, Count, Max, Min, Sum
from django.http import JsonResponse
from django.shortcuts import render

from .models import BillLineItem

HCPCS_URL = "https://clinicaltables.nlm.nih.gov/api/hcpcs/v3/search"
MAX_CODES = 10


class ExternalAPIError(Exception):
    """HCPCS call failed. status = what we send back (502 / 504)."""

    def __init__(self, message, status):
        super().__init__(message)
        self.status = status


def _fetch_hcpcs(term):
    """Returns (total matches, list of {code, description})."""
    try:
        resp = requests.get(
            HCPCS_URL,
            params={"terms": term, "maxList": MAX_CODES, "df": "code,display"},
            timeout=5,
        )
        resp.raise_for_status()
        total, _codes, _extra, rows = resp.json()
        codes = [{"code": code, "description": desc} for code, desc in rows]
    except requests.Timeout:
        raise ExternalAPIError("The HCPCS service took too long to respond.", 504)
    except requests.HTTPError as exc:
        raise ExternalAPIError(f"The HCPCS service returned HTTP {exc.response.status_code}.", 502)
    except requests.RequestException:
        raise ExternalAPIError("Could not reach the HCPCS service.", 502)
    except (ValueError, TypeError):
        raise ExternalAPIError("The HCPCS service returned an unexpected response.", 502)
    return total, codes


def _internal_stats(term):
    """Our side: line items whose description contains the term."""
    items = BillLineItem.objects.filter(description__icontains=term).select_related("bill__provider")
    stats = items.aggregate(
        n=Count("id"),
        total=Sum("charged_amount"),
        avg=Avg("charged_amount"),
        low=Min("charged_amount"),
        high=Max("charged_amount"),
        covered=Sum("estimated_covered_amount"),
        patient=Sum("estimated_patient_responsibility"),
    )
    total = float(stats["total"] or 0)
    covered = float(stats["covered"] or 0)
    return {
        "matching_line_items": stats["n"],
        "total_charged": total,
        "average_charged": round(float(stats["avg"] or 0), 2),
        "min_charged": float(stats["low"] or 0),
        "max_charged": float(stats["high"] or 0),
        "total_covered": covered,
        "patient_responsibility": float(stats["patient"] or 0),
        "coverage_rate_pct": round(covered / total * 100, 1) if total else None,
        "line_items": [
            {
                "bill": item.bill.reference_number,
                "provider": item.bill.provider.name,
                "description": item.description,
                "charged_amount": float(item.charged_amount),
            }
            for item in items
        ],
    }


def _lookup(term):
    total, codes = _fetch_hcpcs(term)
    return {
        "query": term,
        "claimsense": _internal_stats(term),
        "hcpcs": {
            "source": HCPCS_URL,
            "total_matches": total,
            "returned": len(codes),
            "codes": codes,
        },
    }


def api_procedures(request):
    """/api/procedures/?q=imaging -> JSON"""
    term = request.GET.get("q", "").strip()
    if not term:
        return JsonResponse({"error": "Provide a search term, e.g. ?q=imaging"}, status=400)
    try:
        return JsonResponse(_lookup(term))
    except ExternalAPIError as exc:
        return JsonResponse({"error": str(exc), "query": term}, status=exc.status)


def procedure_lookup(request):
    """Same lookup as a normal page."""
    term = request.GET.get("q", "").strip()
    ctx = {"q": term, "result": None, "error": None}
    if term:
        try:
            ctx["result"] = _lookup(term)
        except ExternalAPIError as exc:
            ctx["error"] = str(exc)
    return render(request, "claims/procedure_lookup.html", ctx)
