from django.conf import settings
from django.contrib import messages
from django.contrib.messages.storage.base import Message


def add_hint(request, hint_text, level=settings.HINT_LEVEL):
    if settings.HINTS_ENABLED:
        messages.add_message(request, settings.HINT_LEVEL, hint_text)
