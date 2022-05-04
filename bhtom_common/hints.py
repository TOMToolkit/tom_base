from django.conf import settings
from django.contrib import messages

try:
    HINTS_ENABLED = settings.HINTS_ENABLED
    HINT_LEVEL = settings.HINT_LEVEL
except (AttributeError, KeyError):
    HINTS_ENABLED = False
    HINT_LEVEL = 20


def add_hint(request, hint_text, level=HINT_LEVEL):
    if HINTS_ENABLED:
        messages.add_message(request, level, hint_text)
