"""
Production settings. Used by wsgi.py/asgi.py by default.

ALLOWED_HOSTS is read from the environment so it never needs a code change
to deploy to a new host -- set it as a comma-separated list, e.g.:
    ALLOWED_HOSTS=claimsense.example.com,www.claimsense.example.com
"""

import os

from .base import *  # noqa: F401,F403

DEBUG = False

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("ALLOWED_HOSTS", "").split(",")
    if host.strip()
]
