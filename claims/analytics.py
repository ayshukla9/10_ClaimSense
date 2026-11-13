"""P1 analytics: turn AIRequestLog rows into the metrics and Vega-Lite specs on /analytics/.

The dashboard is question-driven: QUESTIONS lists what we want to know, and build() returns, for each
question, the widget (KPI, chart or table) that answers it. Plain Python statistics, no pandas.
"""
import math
from collections import Counter, defaultdict
from datetime import timedelta
from statistics import mean, median, pstdev

from django.conf import settings
from django.utils import timezone

from .models import AIRequestLog

QUESTIONS = {
    "P1": ("System performance", "How is response time distributed, and how far is the slow tail (p95) from a typical request (p50)?"),
    "P2": ("System performance", "Which kinds of request are slow: model calls vs cached answers vs requests stopped before the model, and does bill size matter?"),
    "P3": ("System performance", "Does a longer answer explain the latency, and is response time stable from day to day?"),
    "U1": ("User behavior", "How often are the AI features used, and is usage growing?"),
    "U2": ("User behavior", "What do users ask about, and which topics does the system fail to answer?"),
    "U3": ("User behavior", "Which exact questions are asked most, and which ones expose gaps in our plan documents?"),
    "U4": ("User behavior", "When do people use the AI (day of week × hour), so we know when load peaks?"),
    "C1": ("Cost", "What does one request cost on our own server, and what would the same tokens cost on a hosted API?"),
    "C2": ("Cost", "Which features and topics consume the most tokens?"),
    "C3": ("Cost", "How does cost move with usage over time, and how much does the 24-hour answer cache save?"),
}

FEATURE_LABEL = dict(AIRequestLog.FEATURES)
FEATURE_COLOR = {"Ask AI": "#2a78d6", "Explain with AI": "#eb6834", "Appeal letter": "#1baf7a"}
OUTCOME = {  # status -> outcome group (shown with an icon-free text label + color in charts)
    "answered": "Answered", "ok": "Answered",
    "not_found": "Not in plan docs", "no_results": "Not in plan docs", "retrieval_only": "Search results only",
    "model_off": "Search results only",
    "rejected": "Blocked (guardrail / limit)", "rate_limited": "Blocked (guardrail / limit)",
    "fallback": "Failed / fallback", "error": "Failed / fallback",
}
OUTCOME_ORDER = ["Answered", "Search results only", "Not in plan docs", "Blocked (guardrail / limit)", "Failed / fallback"]
OUTCOME_COLOR = ["#15803d", "#5b8def", "#9a9a92", "#b45309", "#b91c1c"]
PERIODS = {"7": 7, "30": 30, "90": 90, "all": None}
SOURCES = {"all": "Real + simulated", "real": "Real logs only", "simulated": "Simulated only"}


# ------------------------------------------------------------------ statistics helpers
def pct(values, q):
    """Percentile with linear interpolation (q in 0..100); None for no data."""
    vals = sorted(values)
    if not vals:
        return None
    k = (len(vals) - 1) * q / 100
    lo, hi = math.floor(k), math.ceil(k)
    return vals[lo] + (vals[hi] - vals[lo]) * (k - lo)


def pearson(xs, ys):
    if len(xs) < 3:
        return None
    mx, my = mean(xs), mean(ys)
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if not sx or not sy:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy)


def r2(x, nd=2):
    return None if x is None else round(x, nd)


# ------------------------------------------------------------------ cost model
def compute_usd(row):
    """Estimated server cost of the time the model was busy. Gemini rows are priced as API calls instead."""
    if row["backend"] == "gemini":
        return api_usd(row)
    return row["generation_s"] * settings.ANALYTICS_COMPUTE_USD_PER_HOUR / 3600


def api_usd(row):
    return (row["prompt_tokens"] * settings.ANALYTICS_API_USD_PER_1M_IN
            + row["completion_tokens"] * settings.ANALYTICS_API_USD_PER_1M_OUT) / 1_000_000


def request_type(row):
    f, s = row["feature"], row["status"]
    if f == "ask":
        if row["cached"]:
            return "Ask · cached answer"
        if row["llm_calls"]:
            return "Ask · model answer"
        if s in {"no_results", "rejected", "rate_limited"}:
            return "Ask · stopped before model"
        return "Ask · search only (no model)"
    if f == "explain":
        if row["backend"] == "rules":
            return "Explain · rules only"
        if row["cached"]:
            return "Explain · cached"
        n = row["items"]
        return f"Explain · {n} line item{'s' if n != 1 else ''}" if n < 3 else "Explain · 3+ line items"
    return "Appeal letter (Gemini API)"


# ------------------------------------------------------------------ loading
def load(period="30", source="all", feature="all", now=None):
    now = now or timezone.now()
    qs = AIRequestLog.objects.all()
    days = PERIODS.get(period, 30)
    if days:
        qs = qs.filter(created_at__gte=now - timedelta(days=days))
    if source == "real":
        qs = qs.filter(simulated=False)
    elif source == "simulated":
        qs = qs.filter(simulated=True)
    if feature in FEATURE_LABEL:
        qs = qs.filter(feature=feature)
    rows = list(qs.values("created_at", "feature", "user_id", "plan_type", "question", "topic", "status", "backend",
                          "cached", "llm_calls", "items", "warnings", "retrieval_ms", "generation_s", "total_s",
                          "prompt_tokens", "completion_tokens", "simulated"))
    for r in rows:
        local = timezone.localtime(r["created_at"])
        r["day"] = local.date().isoformat()
        r["weekday"] = local.strftime("%a")
        r["hour"] = local.hour
        r["feature_label"] = FEATURE_LABEL.get(r["feature"], r["feature"])
        r["outcome"] = OUTCOME.get(r["status"], "Failed / fallback")
        r["type"] = request_type(r)
        r["compute_usd"] = compute_usd(r)
        r["api_usd"] = api_usd(r)
        r["tokens"] = r["prompt_tokens"] + r["completion_tokens"]
    return rows


# ------------------------------------------------------------------ the dashboard
def _days_between(rows):
    if not rows:
        return []
    first = min(r["created_at"] for r in rows)
    last = max(r["created_at"] for r in rows)
    d, end, out = timezone.localtime(first).date(), timezone.localtime(last).date(), []
    while d <= end:
        out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def build(rows):
    model_rows = [r for r in rows if r["llm_calls"] and not r["cached"] and r["backend"] != "gemini"]
    lat = [r["total_s"] for r in model_rows]
    days = _days_between(rows)
    n = len(rows)
    out = {"n": n, "questions": QUESTIONS, "real": sum(not r["simulated"] for r in rows),
           "simulated": sum(r["simulated"] for r in rows)}

    # ---------------- performance
    p50, p95 = pct(lat, 50), pct(lat, 95)
    sd = pstdev(lat) if len(lat) > 1 else None
    cv = sd / mean(lat) if sd is not None and mean(lat) else None
    degraded = sum(r["outcome"] == "Failed / fallback" for r in rows)
    out["perf"] = {
        "model_requests": len(model_rows), "p50": r2(p50), "p95": r2(p95), "mean": r2(mean(lat)) if lat else None,
        "tail_ratio": r2(p95 / p50, 1) if p50 else None, "cv": r2(cv), "degraded_pct": r2(100 * degraded / n, 1) if n else None,
        "cached_p50": r2(pct([r["total_s"] for r in rows if r["cached"]], 50), 3),
    }
    by_type = defaultdict(list)
    for r in rows:
        by_type[r["type"]].append(r["total_s"])
    type_rows = sorted(({"type": t, "n": len(v), "median": round(median(v), 3), "p95": round(pct(v, 95), 3),
                         "mean": round(mean(v), 3)} for t, v in by_type.items()), key=lambda x: -x["median"])
    out["perf"]["by_type"] = type_rows
    xs = [r["completion_tokens"] for r in model_rows if r["completion_tokens"]]
    ys = [r["total_s"] for r in model_rows if r["completion_tokens"]]
    out["perf"]["r_tokens_latency"] = r2(pearson(xs, ys))
    daily_lat = []
    for d in days:
        v = [r["total_s"] for r in model_rows if r["day"] == d]
        if v:
            daily_lat += [{"day": d, "stat": "p50 (median)", "seconds": round(pct(v, 50), 2)},
                          {"day": d, "stat": "p95", "seconds": round(pct(v, 95), 2)}]
    out["perf"]["daily"] = daily_lat

    # ---------------- user behavior
    users = {r["user_id"] for r in rows if r["user_id"]}
    unanswered = sum(r["outcome"] in {"Not in plan docs", "Search results only"} for r in rows if r["feature"] == "ask")
    asks = sum(r["feature"] == "ask" for r in rows)
    per_day = Counter(r["day"] for r in rows)
    totals = [per_day.get(d, 0) for d in days]
    ma = [{"day": d, "ma7": round(mean(totals[max(0, i - 6):i + 1]), 2)} for i, d in enumerate(days)]
    half = len(totals) // 2
    growth = None
    if half >= 3 and sum(totals[:half]):
        growth = 100 * (mean(totals[half:]) - mean(totals[:half])) / mean(totals[:half])
    out["users"] = {"requests": n, "per_day": r2(n / len(days), 1) if days else None, "active_users": len(users),
                    "unanswered_pct": r2(100 * unanswered / asks, 1) if asks else None, "growth_pct": r2(growth, 0),
                    "days": len(days)}
    topic_counts = Counter((r["topic"], r["outcome"]) for r in rows if r["feature"] == "ask")
    out["users"]["topics"] = [{"topic": t, "outcome": o, "n": c} for (t, o), c in topic_counts.items()]
    q_stats = defaultdict(list)
    for r in rows:
        if r["feature"] == "ask" and r["question"]:
            q_stats[r["question"].strip().rstrip("?").lower()].append(r)
    top = sorted(q_stats.values(), key=len, reverse=True)[:8]
    out["users"]["top_questions"] = [{"question": v[0]["question"], "n": len(v), "topic": v[0]["topic"],
                                      "answered_pct": round(100 * sum(x["outcome"] == "Answered" for x in v) / len(v))}
                                     for v in top]
    gaps = [v for v in q_stats.values() if any(x["outcome"] == "Not in plan docs" for x in v)]
    gaps.sort(key=lambda v: -sum(x["outcome"] == "Not in plan docs" for x in v))
    out["users"]["gaps"] = [{"question": v[0]["question"], "n": sum(x["outcome"] == "Not in plan docs" for x in v),
                             "topic": v[0]["topic"]} for v in gaps[:6]]
    heat = Counter((r["weekday"], r["hour"]) for r in rows)
    out["users"]["heat"] = [{"weekday": w, "hour": h, "n": c} for (w, h), c in heat.items()]
    out["users"]["daily"] = [{"day": r["day"], "feature": r["feature_label"]} for r in rows]
    out["users"]["ma"] = ma

    # ---------------- cost
    compute_total = sum(r["compute_usd"] for r in rows)
    api_total = sum(r["api_usd"] for r in rows)
    tokens = sum(r["tokens"] for r in rows)
    avg_uncached = defaultdict(list)
    for r in rows:
        if r["llm_calls"] and not r["cached"]:
            avg_uncached[r["feature"]].append(r)
    saved_compute = saved_api = 0.0
    cached_n = 0
    for r in rows:
        if r["cached"] and avg_uncached.get(r["feature"]):
            ref = avg_uncached[r["feature"]]
            saved_compute += mean(x["compute_usd"] for x in ref)
            saved_api += mean(x["api_usd"] for x in ref)
            cached_n += 1
    out["cost"] = {
        "tokens": tokens, "compute_total": compute_total, "api_total": api_total,
        "compute_per_1k": 1000 * compute_total / n if n else None, "api_per_1k": 1000 * api_total / n if n else None,
        "tokens_per_model_request": round(mean(r["tokens"] for r in model_rows)) if model_rows else None,
        "cache_hits": cached_n, "cache_saved_pct": r2(100 * saved_compute / (compute_total + saved_compute), 1)
        if compute_total + saved_compute else None,
        "rate": settings.ANALYTICS_COMPUTE_USD_PER_HOUR, "api_model": settings.ANALYTICS_API_MODEL,
        "api_in": settings.ANALYTICS_API_USD_PER_1M_IN, "api_out": settings.ANALYTICS_API_USD_PER_1M_OUT,
    }
    tok = defaultdict(lambda: [0, 0, 0, 0.0, 0.0, 0.0])  # prompt, completion, n, compute $, api $, seconds
    for r in rows:
        if r["tokens"]:
            key = r["topic"] if r["feature"] == "ask" else r["feature_label"]
            v = tok[key]
            v[0] += r["prompt_tokens"]
            v[1] += r["completion_tokens"]
            v[2] += 1
            v[3] += r["compute_usd"]
            v[4] += r["api_usd"]
            v[5] += r["generation_s"]
    out["cost"]["tokens_by"] = [{"group": g, "kind": kind, "tokens": v[i]} for g, v in tok.items()
                                for i, kind in ((0, "Prompt (input)"), (1, "Completion (output)"))]
    out["cost"]["tokens_table"] = sorted((
        {"group": g, "requests": v[2], "per_request": round((v[0] + v[1]) / v[2]), "seconds": round(v[5] / v[2], 1),
         "compute_per_1k": 1000 * v[3] / v[2], "api_per_1k": 1000 * v[4] / v[2]}
        for g, v in tok.items()), key=lambda x: -x["compute_per_1k"])
    daily_cost = []
    for d in days:
        day_rows = [r for r in rows if r["day"] == d]
        daily_cost += [{"day": d, "series": "Our server (compute estimate)", "usd": round(sum(r["compute_usd"] for r in day_rows), 6)},
                       {"day": d, "series": f"Hosted API equivalent ({settings.ANALYTICS_API_MODEL})", "usd": round(sum(r["api_usd"] for r in day_rows), 6)}]
    out["cost"]["daily"] = daily_cost
    out["specs"] = specs(out, rows, model_rows)
    return out


# ------------------------------------------------------------------ Vega-Lite specs (data inline)
def _base(values, **spec):
    return {"$schema": "https://vega.github.io/schema/vega-lite/v5.json", "data": {"values": values},
            "width": "container", **spec}


def specs(out, rows, model_rows):
    feat_scale = {"domain": list(FEATURE_COLOR), "range": list(FEATURE_COLOR.values())}
    s = {}
    s["P1"] = _base([{"seconds": r["total_s"], "feature": r["feature_label"]} for r in model_rows], height=220,
                    mark={"type": "bar", "cornerRadiusEnd": 3, "binSpacing": 2},
                    encoding={"x": {"bin": {"maxbins": 24}, "field": "seconds", "title": "Seconds per request (model calls, not cached)"},
                              "y": {"aggregate": "count", "title": "Requests"},
                              "color": {"field": "feature", "title": "Feature", "scale": feat_scale},
                              "tooltip": [{"aggregate": "count", "title": "Requests"}, {"field": "feature"}]})
    if out["perf"]["p95"] is not None:
        rules = [{"seconds": out["perf"]["p50"], "label": f"p50 {out['perf']['p50']} s"},
                 {"seconds": out["perf"]["p95"], "label": f"p95 {out['perf']['p95']} s"}]
        hist = {k: v for k, v in s["P1"].items() if k not in ("$schema", "data", "width", "height")}
        s["P1"] = _base(None, height=220, layer=[
            {"data": {"values": [{"seconds": r["total_s"], "feature": r["feature_label"]} for r in model_rows]}, **hist},
            {"data": {"values": rules}, "mark": {"type": "rule", "strokeDash": [5, 4], "strokeWidth": 2, "color": "#0b0b0b"},
             "encoding": {"x": {"field": "seconds", "type": "quantitative"}}},
            {"data": {"values": rules}, "mark": {"type": "text", "align": "left", "dx": 4, "dy": -6, "fontSize": 11, "color": "#0b0b0b"},
             "encoding": {"x": {"field": "seconds", "type": "quantitative"}, "y": {"value": 8}, "text": {"field": "label"}}}])
        s["P1"]["data"] = {"values": []}
    s["P2"] = _base(out["perf"]["by_type"], height={"step": 26},
                    layer=[{"mark": {"type": "bar", "color": "#2a78d6", "cornerRadiusEnd": 3},
                            "encoding": {"x": {"field": "median", "type": "quantitative", "title": "Seconds (bar = median, tick = p95, log scale)",
                                               "scale": {"type": "symlog"}},
                                         "y": {"field": "type", "type": "nominal", "sort": "-x", "title": None},
                                         "tooltip": [{"field": "type"}, {"field": "n", "title": "requests"},
                                                     {"field": "median", "title": "median s"}, {"field": "p95", "title": "p95 s"}]}},
                           {"mark": {"type": "tick", "color": "#0b0b0b", "thickness": 2, "size": 18},
                            "encoding": {"x": {"field": "p95", "type": "quantitative"}, "y": {"field": "type", "type": "nominal", "sort": "-x"}}},
                           {"mark": {"type": "text", "align": "left", "dx": 6, "fontSize": 11},
                            "encoding": {"x": {"field": "p95", "type": "quantitative"}, "y": {"field": "type", "type": "nominal", "sort": "-x"},
                                         "text": {"field": "n", "format": ",", "title": "n"}}}])
    s["P3a"] = _base([{"tokens": r["completion_tokens"], "seconds": r["total_s"], "feature": r["feature_label"]}
                      for r in model_rows if r["completion_tokens"]], height=220,
                     mark={"type": "point", "filled": True, "size": 60, "opacity": 0.7},
                     encoding={"x": {"field": "tokens", "type": "quantitative", "title": "Output tokens generated"},
                               "y": {"field": "seconds", "type": "quantitative", "title": "Seconds"},
                               "color": {"field": "feature", "title": "Feature", "scale": feat_scale},
                               "tooltip": [{"field": "feature"}, {"field": "tokens"}, {"field": "seconds"}]})
    s["P3b"] = _base(out["perf"]["daily"], height=220, mark={"type": "line", "point": True, "strokeWidth": 2},
                     encoding={"x": {"field": "day", "type": "temporal", "title": None},
                               "y": {"field": "seconds", "type": "quantitative", "title": "Seconds (model calls)"},
                               "color": {"field": "stat", "title": None, "scale": {"range": ["#2a78d6", "#eb6834"]}},
                               "tooltip": [{"field": "day", "type": "temporal"}, {"field": "stat"}, {"field": "seconds"}]})
    s["U1"] = _base(None, height=230, layer=[
        {"data": {"values": out["users"]["daily"]}, "mark": {"type": "bar", "opacity": 0.85},
         "encoding": {"x": {"field": "day", "type": "temporal", "timeUnit": "yearmonthdate", "title": None},
                      "y": {"aggregate": "count", "title": "Requests per day"},
                      "color": {"field": "feature", "title": "Feature", "scale": feat_scale},
                      "tooltip": [{"field": "day", "type": "temporal", "timeUnit": "yearmonthdate"}, {"field": "feature"},
                                  {"aggregate": "count", "title": "requests"}]}},
        {"data": {"values": out["users"]["ma"]}, "mark": {"type": "line", "color": "#0b0b0b", "strokeWidth": 2},
         "encoding": {"x": {"field": "day", "type": "temporal", "timeUnit": "yearmonthdate"},
                      "y": {"field": "ma7", "type": "quantitative"},
                      "tooltip": [{"field": "day", "type": "temporal"}, {"field": "ma7", "title": "7-day average"}]}}])
    s["U1"]["data"] = {"values": []}
    s["U2"] = _base(out["users"]["topics"], height={"step": 26}, mark={"type": "bar"},
                    encoding={"y": {"field": "topic", "type": "nominal", "sort": "-x", "title": None},
                              "x": {"aggregate": "sum", "field": "n", "type": "quantitative", "title": "Questions", "stack": "zero"},
                              "color": {"field": "outcome", "title": "Outcome",
                                        "scale": {"domain": OUTCOME_ORDER, "range": OUTCOME_COLOR}},
                              "order": {"field": "outcome"},
                              "tooltip": [{"field": "topic"}, {"field": "outcome"}, {"aggregate": "sum", "field": "n", "title": "questions"}]})
    s["U4"] = _base(out["users"]["heat"], height=170, mark={"type": "rect", "cornerRadius": 2},
                    encoding={"x": {"field": "hour", "type": "ordinal", "title": "Hour of day", "scale": {"domain": list(range(24))}},
                              "y": {"field": "weekday", "type": "ordinal", "title": None,
                                    "sort": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]},
                              "color": {"field": "n", "type": "quantitative", "title": "Requests",
                                        "scale": {"scheme": "blues"}},
                              "tooltip": [{"field": "weekday"}, {"field": "hour"}, {"field": "n", "title": "requests"}]})
    s["C2"] = _base(out["cost"]["tokens_by"], height={"step": 26}, mark={"type": "bar"},
                    encoding={"y": {"field": "group", "type": "nominal", "sort": "-x", "title": None},
                              "x": {"aggregate": "sum", "field": "tokens", "type": "quantitative", "title": "Tokens"},
                              "color": {"field": "kind", "title": None, "scale": {"range": ["#2a78d6", "#eb6834"]}},
                              "tooltip": [{"field": "group"}, {"field": "kind"}, {"aggregate": "sum", "field": "tokens", "format": ","}]})
    s["C3"] = _base(out["cost"]["daily"], height=220, mark={"type": "line", "point": True, "strokeWidth": 2},
                    encoding={"x": {"field": "day", "type": "temporal", "title": None},
                              "y": {"field": "usd", "type": "quantitative", "title": "US dollars per day", "axis": {"format": "$.3f"}},
                              "color": {"field": "series", "title": None, "scale": {"range": ["#2a78d6", "#eb6834"]}},
                              "tooltip": [{"field": "day", "type": "temporal"}, {"field": "series"}, {"field": "usd", "format": "$.5f"}]})
    return s
