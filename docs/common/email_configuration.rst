Email Configuration
===================

When configured, TOM Toolkit sends emails for registration requests,
registration approval notices, and password resets.

Email delivery is a Django feature. There are no TOM Toolkit-specific email settings.
See Django's `Sending email <https://docs.djangoproject.com/en/5.2/topics/email/>`_
topic guide for details.  This section aims to put the Django configuration in
a TOM Toolkit context. Email is not configured out of the box.

.. Note::
   **These instructions will change**. This page describes email configuration as of
   Django 5.2. Django's email framework is being moderized over the current (6.1) and
   future releases:

   - Django 6.0 rebuilt ``django.core.mail`` on Python's modern email API and deprecated
     the ``(name, address)`` tuple form of ``MANAGERS`` and ``ADMINS`` that we show below.
   - Django 6.1 introduced a ``MAILERS`` setting dictionary, similar to
     the ``DATABASES`` and ``CACHES`` configuration dictionaries.
   - Django 7.0 removes ``EMAIL_BACKEND`` and the other ``EMAIL_*`` settings, the settings
     we describe here.

   Expect this page to change as TOM Toolkit moves to those releases
   (see the `Django 6.0 <https://docs.djangoproject.com/en/6.1/releases/6.0/>`_ and
   `Django 6.1 <https://docs.djangoproject.com/en/6.1/releases/6.1/>`_ release notes).


We'll start with a short tutorial. To go directly to the configuration of your TOM and
skip the tutorial, see :ref:`email-configuration-in-tom-toolkit`.

-----------------
A short tutorial
-----------------

Django has a ``sendtestemail`` management command. Let's start by trying to send an email::

   ./manage.py sendtestemail

Unless you've already done some
configuration, that didn't work. Try this::

   ./manage.py sendtestemail --help

Notice the ``--managers`` and ``--admins`` options and their references to ``settings.MANAGERS`` and
``settings.ADMINS``.

Let's configure those in your ``settings.py``. We'll configure an ``EMAIL_BACKEND`` while
we're at it::

  MANAGERS = [("Mary", "mary@example.com"),]
  ADMINS = [("John", "john@example.com"),]
  EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

The `console.EMAIL_BACKEND <https://docs.djangoproject.com/en/5.2/topics/email/#console-backend>`_
we've configured doesn't send email. Rather, it outputs to stdout. With those settings, let's try again::

  ./manage.py sendtestemail --managers

Now, in the *console*, you should see something like this::

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

.. _email-configuration-in-tom-toolkit:

---------------------------------
Configuring Email in TOM Toolkit
---------------------------------

Your TOM uses email for these optional features:

- **Registration requests**: with ``TOM_REGISTRATION_STRATEGY = 'approval_required'``, the addresses in
  Django's `MANAGERS <https://docs.djangoproject.com/en/5.2/ref/settings/#managers>`_ setting are
  notified of each sign-up awaiting approval.
- **Approval notices**: the new user is notified when a superuser approves their account.
- **Password reset**: ``TOM_PASSWORD_RESET_ENABLED = True`` adds the "Forgot your password?" flow.

(See :doc:`Accounts and Authentication <authentication>` for descriptions of the features themselves.)

When email is not configured, or a send fails, guidance is provided in the UI.
(See `What happens when email is not configured or  when sends fail`_ below).

Configuring the backend
-------------------------

Email delivery is standard Django and TOM Toolkit adds no email settings of its own. The complete
reference is Django's `Sending email <https://docs.djangoproject.com/en/5.2/topics/email/>`_
topic guide.

In the tutorial section above, we configured an email backend that prints to stdout, which is useful
for development. For production, point Django's SMTP backend (the default) at your mail relay, and
say who your TOM's mail comes from and who its administrators are::

    # from your email provider
    EMAIL_HOST = 'smtp.example.org'  # your institution's or provider's SMTP relay
    EMAIL_PORT = 587
    EMAIL_HOST_USER = 'tom@example.org'
    EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')  # keep secrets out of settings.py
    EMAIL_USE_TLS = True
    #
    DEFAULT_FROM_EMAIL = 'tom@example.org'  # the From: address on everything the TOM sends
    MANAGERS = [('TOM admins', 'admins@example.org')]  # registration requests go here

The host, port, credentials and TLS mode come from your email provider; what each setting means is
in Django's `email settings reference
<https://docs.djangoproject.com/en/5.2/ref/settings/#email-backend>`_.

Verifying your configuration
----------------------------

As seen in the tutorial above, Django includes a management command that sends a test message
through whatever backend you configured::

    ./manage.py sendtestemail you@example.org

To try the SMTP configuration without involving a real relay, you can run a small SMTP server on
your own machine: the ``aiosmtpd`` package (``pip install aiosmtpd``) accepts SMTP connections and
prints each received message to its terminal. To run it, in a terminal type::

    python -m aiosmtpd -n -l localhost:8025

Configure your ``settings.py`` to point at it (``EMAIL_HOST = 'localhost'``, ``EMAIL_PORT = 8025``),
and ``sendtestemail`` output should appear in the (`aiosmtpd`) terminal.

-------------------------------------------------------------------
What happens when email is not configured or  when sends fail
-------------------------------------------------------------------

Your TOM's Email configuration can be verifiied in code and at the command line:

- TOM Toolkit determines whether email is configured with a heuristic predicate
  (``tom_common.accounts.email.email_is_configured``). Any backend other than Django's SMTP
  default counts as configured. (The SMTP default pointed at ``localhost`` with no credentials is
  treated as "not configured").
- ``manage.py check`` warns (``tom_common.W002``) when approval-required registration or password
  reset is enabled without a configured email backend.

When sending email fails, feedback is given in the UI and logs:

- Approving a registration always succeeds even when the notice cannot be sent. Under those
  circumstances, the approver is told in the UI to notify the user directly. Additionally, the
  *Pending users* table indicates when email is not configured.
- A failed password-reset send is reported on the page, with the failure logged for the operator.

------------------------
Customizing the emails
------------------------

Each email is composed from  a pair of templates (``*_subject.txt`` and ``*_message.txt``). The
templates can be customized (overridden) by placing your own copy in your TOM's
``templates/`` directory (sibling to ``manage.py``).
The sender address is set by ``DEFAULT_FROM_EMAIL``.

- **Registration request** email goes to the addresses in ``MANAGERS``. The default templates are
  set by TOM Toolkit. To customize, put your overriding templates in
  ``account/email/registration_requested_subject.txt`` and ``_message.txt``.
- **Approval notice** email goes to the approved user. The default templates are set by TOM Toolkit.
  To customize, put your overriding templates in
  ``account/email/registration_approved_subject.txt`` and ``_message.txt``.
- **Password reset** email goes to the email address of the account being reset. The default templates
  are set by ``django-allauth``. To customize, put your  overriding templates in
  ``account/email/password_reset_key_subject.txt`` and ``_message.txt``.

