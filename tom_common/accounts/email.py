"""Reasoning about this TOM's email configuration.

Registration approval and password reset degrade gracefully without email — the pages and
messages tell administrators to notify users directly — but email is the smooth-path
prerequisite, so several places want to know whether it exists.
"""
from __future__ import annotations

from django.conf import settings

DEFAULT_SMTP_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'


def email_is_configured() -> bool:
    """Best-effort answer to "can this TOM deliver email?".

    Heuristic: Django's default SMTP backend pointed at the default localhost with no
    credentials is the nobody-configured-email signature. Any other backend (console, file,
    locmem, a real relay) was chosen on purpose and counts as configured.
    """
    backend = getattr(settings, 'EMAIL_BACKEND', DEFAULT_SMTP_BACKEND)
    if backend != DEFAULT_SMTP_BACKEND:
        return True
    return not (settings.EMAIL_HOST == 'localhost' and not settings.EMAIL_HOST_USER)
