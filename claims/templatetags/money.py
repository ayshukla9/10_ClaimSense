"""Currency formatting for templates: {% load money %} ... {{ amount|money }} -> $1,800.00"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django import template

register = template.Library()


@register.filter
def money(value, empty="—"):
    """Format a number as US dollars with thousands separators and two decimals.

    None or an unparsable value renders as `empty` (an em dash by default).
    """
    if value is None or value == "":
        return empty
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        return empty
    sign = "-" if amount < 0 else ""
    return f"{sign}${abs(amount):,.2f}"
