"""Registration and authentication logic for TOM Toolkit.

This subpackage collects the account-related pieces of tom_common in one place:

- ``adapters``: the django-allauth adapters (registration policy, TOTP-secret encryption,
  issuer name, authenticator-removal policy) — the seam a TOM subclasses to change behaviour.
- ``urlpatterns``: helpers deciding which allauth routes are mounted (password reset is
  opt-in via ``TOM_PASSWORD_RESET_ENABLED``).
- ``requirements``: the ``TOM_ACCOUNT_REQUIREMENTS`` post-login checks.
- ``password_validation``: validators for ``AUTH_PASSWORD_VALIDATORS``.
- ``api_auth``: DRF token authentication with expiry and MFA gating.

The middleware consuming these stays in ``tom_common.middleware`` (its dotted paths are
hand-listed in deployed TOMs' settings), and signal receivers stay in ``tom_common.signals``.
"""
