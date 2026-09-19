Email Configuration
===================

Email delivery is a Django feature. There are no TOM Toolkit-secific email settings.
See Django's `Sending email <https://docs.djangoproject.com/en/stable/topics/email/>`_
topic guide for all the details.  This section only puts the configuration in a TOM Toolkit
context.

Email is not configured out of the box. When configured, TOM Toolkit sends emails for
registration requests, registration approval notices, and password resets. To go directly
to the configuration of you TOM and skip the following short tutorial, click here.

-----------------
A short tutorial
-----------------

Let's start by trying to send an email::

   ./manage.py sendtestemail

Django has a ``sendtestemail`` management command. Unless you've already done some
configuration, that didn't work. Try this::

   ./manage.py sendtestemail --help

Notice the ``--managers`` and ``--admins`` options and their references to ``settings.MANAGERS`` and
``settings.ADMINS``, respectively.

Let's configure those in your ``settings.py`` (and an ``EMAIL_BACKEND`` while we're at it)::

  MANAGERS = [("Mary", "mary@example.com"),]
  ADMINS = [("John", "john@example.com"),]
  EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

With those settings, try it again::

  ./manage.py sendtestemail --managers

In the *console* (consider the backend we've configured), you should see something like this::

  Content-Type: text/plain; charset="utf-8"
  MIME-Version: 1.0
  Content-Transfer-Encoding: 7bit
  Subject: [Django] Test email from tomtoolkit-host on 2026-09-19
   00:32:32.742613+00:00
  From: root@localhost
  To: mary@example.com
  Date: Sat, 19 Sep 2026 00:32:32 -0000
  Message-ID: <178977795274.2655038.15656462345865752721@tomtoolkit-host>
  
  This email was sent to the site managers.
  -------------------------------------------------------------------------------

------------------------




Your TOM uses email for a small set of optional features:

- **Registration requests**: with ``TOM_REGISTRATION_STRATEGY = 'approval_required'``, the addresses in
  Django's `MANAGERS <https://docs.djangoproject.com/en/stable/ref/settings/#managers>`_ setting are
  notified of each sign-up awaiting approval.
- **Approval notices**: the new user is notified when a superuser approves their account.
- **Password reset**: ``TOM_PASSWORD_RESET_ENABLED = True`` adds the "Forgot your password?" flow.

(See :doc:`Accounts and Authentication <authentication>` for the features themselves.)

Emails are sent whenever an email backend is configured — there is no separate on/off switch.
For TOMs migrating from ``tom_registration``, this is one less configuration value: the old
``SEND_APPROVAL_EMAILS`` toggle has no replacement because none is needed. When email is not
configured, or a send fails, the features degrade with guidance in the UI rather than breaking
(see `Without email, and when sends fail`_ below).

Configuring the backend
-----------------------

Email delivery is standard Django — TOM Toolkit adds no email settings of its own. The complete
reference is Django's `Sending email <https://docs.djangoproject.com/en/stable/topics/email/>`_
topic guide; this section only puts the settings in TOM context.

For development, the console backend prints every message to the ``runserver`` terminal::

    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

For production, point Django's SMTP backend (the default) at your mail relay, and say who your
TOM's mail comes from and who its administrators are::

    EMAIL_HOST = 'smtp.example.org'         # your institution's or provider's SMTP relay
    EMAIL_PORT = 587
    EMAIL_HOST_USER = 'tom@example.org'
    EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')  # keep secrets out of settings.py
    EMAIL_USE_TLS = True
    DEFAULT_FROM_EMAIL = 'tom@example.org'  # the From: address on everything the TOM sends
    MANAGERS = [('TOM admins', 'admins@example.org')]  # registration requests go here

The host, port, credentials and TLS mode come from your email provider; what each setting means is
in Django's `email settings reference
<https://docs.djangoproject.com/en/stable/ref/settings/#email-backend>`_.

Verifying your configuration
----------------------------

Django ships a management command that sends a test message through whatever backend you
configured::

    ./manage.py sendtestemail you@example.org

To try the SMTP configuration without involving a real relay, you can run a small SMTP server on
your own machine: the ``aiosmtpd`` package (``pip install aiosmtpd``) accepts SMTP connections and
prints each received message to its terminal. Run it in one terminal::

    python -m aiosmtpd -n -l localhost:8025

point your ``settings.py`` at it (``EMAIL_HOST = 'localhost'``, ``EMAIL_PORT = 8025``), and
``sendtestemail`` — and every email your TOM sends — appears in that terminal.

Without email, and when sends fail
----------------------------------

The email features degrade rather than break:

- The toolkit judges whether email is configured with a heuristic
  (``tom_common.accounts.email.email_is_configured``): any backend other than Django's SMTP
  default counts as configured; the SMTP default pointed at ``localhost`` with no credentials is
  treated as "nobody configured email".
- ``manage.py check`` warns (``tom_common.W002``) when approval-required registration or password
  reset is enabled without a configured backend.
- Approving a registration always succeeds even when the notice cannot be sent: the approver is
  told in the UI to notify the user directly, and the *Pending users* table says when email is not
  configured.
- A failed password-reset send is reported on the page, with the failure logged for the operator,
  instead of producing a server error.

Customizing the emails
----------------------

The registration emails render from templates you can override in your project's ``templates/``
directory (the one sibling to ``manage.py``): ``account/email/registration_requested_subject.txt``
and ``_message.txt`` go to ``MANAGERS``; ``account/email/registration_approved_subject.txt`` and
``_message.txt`` go to the approved user. The sender address is ``DEFAULT_FROM_EMAIL``.
Password-reset emails are django-allauth's; override its ``account/email/password_reset_key_*``
templates the same way.
