"""P1-A4 Part 1: Vega-Lite charts."""
import json

import vl_convert as vlc
from django.conf import settings
from django.http import Http404, HttpResponse
from django.shortcuts import render

from . import summaries

SPEC_DIR = settings.BASE_DIR / "static" / "vega-lite"

# chart name -> (spec file, function that gives the same rows as the API url in the spec)
CHARTS = {
    "chart1": ("charged_per_provider.vl.json", summaries.provider_summary),
    "chart2": ("charges_over_time.vl.json", summaries.bill_summary),
}


def vega_page(request):
    return render(request, "claims/vega_charts.html")


def vega_chart_png(request, name):
    """
    /vega-lite/chart1.png etc. -- same spec as the page, rendered to PNG.

    The spec file uses data.url, but here we swap in the rows directly,
    otherwise the server would have to call its own API (which can hang on
    PythonAnywhere since the free plan only has one worker).
    """
    if name not in CHARTS:
        raise Http404("Unknown chart")
    spec_file, rows = CHARTS[name]
    spec = json.loads((SPEC_DIR / spec_file).read_text(encoding="utf-8"))
    spec["data"] = {"values": rows()}
    png = vlc.vegalite_to_png(json.dumps(spec), scale=2)
    return HttpResponse(png, content_type="image/png")
