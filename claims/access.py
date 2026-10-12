"""Authentication and explicit patient ownership policy."""
from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponseForbidden, JsonResponse
from django.views.decorators.cache import never_cache


def visible_bills(user):
    from .models import Bill
    qs = Bill.objects.all()
    if not user.is_authenticated:
        return qs.none()
    return qs if user.is_staff else qs.filter(patient__user=user)


def visible_providers(user):
    from .models import Provider
    qs = Provider.objects.all()
    if not user.is_authenticated:
        return qs.none()
    return qs if user.is_staff else qs.filter(insurance_plan__patient__user=user)


def private_view(view, *, api=False, staff_only=False):
    @never_cache
    @wraps(view)
    def guarded(request, *args, **kwargs):
        if not request.user.is_authenticated:
            if api:
                return JsonResponse({"error": "Authentication required"}, status=401)
            return redirect_to_login(request.get_full_path())
        if staff_only and not request.user.is_staff:
            return HttpResponseForbidden("Staff access required for record management.")
        return view(request, *args, **kwargs)
    return guarded
