"""P1 analytics dashboard: /analytics/ (staff only; wrapped by access.private_view in urls.py)."""
from django.shortcuts import render

from . import analytics
from .models import AIRequestLog


def ai_analytics(request):
    period = request.GET.get("period", "30") if request.GET.get("period") in analytics.PERIODS else "30"
    source = request.GET.get("source", "all") if request.GET.get("source") in analytics.SOURCES else "all"
    feature = request.GET.get("feature", "all") if request.GET.get("feature") in dict(AIRequestLog.FEATURES) else "all"
    data = analytics.build(analytics.load(period, source, feature))
    return render(request, "claims/ai_analytics.html", {
        "d": data, "period": period, "source": source, "feature": feature,
        "periods": [("7", "Last 7 days"), ("30", "Last 30 days"), ("90", "Last 90 days"), ("all", "All time")],
        "sources": list(analytics.SOURCES.items()),
        "features": [("all", "All features")] + list(AIRequestLog.FEATURES),
    })
