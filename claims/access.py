"""Central route policy: anonymous users cannot query patient records.

Public signup creates a normal account, not an approved patient-record operator.
Existing staff/superusers retain access; administrators approve team accounts.
"""
from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponseForbidden, JsonResponse
from django.views.decorators.cache import never_cache


def private_view(view, *, api=False):
    @never_cache
    @wraps(view)
    def guarded(request, *args, **kwargs):
        if not request.user.is_authenticated:
            if api:
                return JsonResponse({"error": "Authentication required"}, status=401)
            return redirect_to_login(request.get_full_path())
        if not request.user.is_staff:
            if api:
                return JsonResponse({"error": "Staff approval required"}, status=403)
            return HttpResponseForbidden("Staff approval is required to access patient records.")
        return view(request, *args, **kwargs)
    return guarded
