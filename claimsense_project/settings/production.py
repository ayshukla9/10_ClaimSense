"""
Production settings. Used by wsgi.py/asgi.py by default.

ALLOWED_HOSTS is read from the environment so it never needs a code change
to deploy to a new host -- set it as a comma-separated list, e.g.:
    ALLOWED_HOSTS=claimsense.example.com,www.claimsense.example.com
When unset it falls back to any *.pythonanywhere.com host.
"""

import os

from .base import *  # noqa: F401,F403

DEBUG = False

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("ALLOWED_HOSTS", ".pythonanywhere.com").split(",")
    if host.strip()
]


# Cache busting (P1-A3 Section 3 bonus): hashed filenames after collectstatic
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"},
}
