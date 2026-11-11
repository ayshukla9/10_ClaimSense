"""Small presentation helpers: {% load ui %}"""
import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

PLACEHOLDER = re.compile(r"\[([A-Za-z][^\[\]\n]{0,40})\]")


@register.filter
def flag_help(label):
    """Plain-English meaning of a flag badge label ("Out of network" -> one sentence)."""
    from claims.bill_insights import issue_help
    return issue_help(label)


@register.filter
def highlight_placeholders(text):
    """Escape text, then wrap [Your name]-style placeholders in <mark> so they stand out."""
    escaped = escape(text or "")
    return mark_safe(PLACEHOLDER.sub(r'<mark class="placeholder">[\1]</mark>', escaped))
