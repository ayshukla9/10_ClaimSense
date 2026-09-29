"""Section 4: server-side Matplotlib chart served as a PNG."""
import io

import matplotlib

matplotlib.use("Agg")  # headless backend, required on servers
import matplotlib.pyplot as plt
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import render

from .models import Provider


def charts_page(request):
    return render(request, "claims/charts.html")


def bills_per_provider_png(request):
    data = list(Provider.objects.annotate(n=Count("bills")).values_list("name", "n"))
    fig, ax = plt.subplots(figsize=(7, 4))
    if data:
        labels, counts = zip(*data)
        ax.bar(labels, counts, color="#13294b", label="Bills")
        ax.legend()
    ax.set_title("Bills per Provider")
    ax.set_xlabel("Provider")
    ax.set_ylabel("Number of bills")
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
    buf = io.BytesIO()  # in-memory: no temp file on disk
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)  # release figure memory
    return HttpResponse(buf.getvalue(), content_type="image/png")
