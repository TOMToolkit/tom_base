import base64

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

from django.conf import settings
from django.db.models.signals import post_save
from django.db import models
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.contrib.auth.signals import user_logged_in, user_logged_out

from rest_framework.authtoken.models import Token


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_auth_token(sender, instance=None, created=False, **kwargs):
    if created:
        Token.objects.create(user=instance)


# Signal: Set cipher on login
@receiver(user_logged_in)
def set_cipher_on_login(sender, request, user, **kwargs):
    """When the user logs in, capture their password and use it to
    generate and cache a Fernet instance for user-specific encryption."""
    if hasattr(user, "profile"):
        password = request.POST.get("password")  # Capture password from login
        if password:
            user.profile.create_cipher(password)  # Generates and caches the Fernet instance


# Signal: Clear cipher on logout
@receiver(user_logged_out)
def clear_cipher_on_logout(sender, request, user, **kwargs):
    """Clear the cipher when a user logs out."""
    if hasattr(user, "profile"):
        user.profile.clear_cipher()


class Profile(models.Model):
    """Profile model for a TOMToolkit User"""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    affiliation = models.CharField(max_length=100, null=True, blank=True)

    # Here, we're setting up a mechanism to encrypt sensitive User data like
    # API keys and password for Facilities and data services, etc. The Signals
    # above create and clear the _cipher upon login and logout, respectively.
    # We use the user_logged_in signal to intercept the User's password and
    # use that to derive the encryption_key and use that to create the cipher.
    _cipher: Fernet = None

    @property
    def cipher(self) -> Fernet:
        """Return the User's Fernet cipher"""
        if self._cipher is None:
            # TODO: if this should occur, lazily instantiate - must prompt user for password
            raise ValueError("Cipher not created. Please create it with a password.")
        return self._cipher

    def create_cipher(self, password: str):
        """Create a Fernet cipher and save it to be used to encrypt API keys and
        other external service credentials for this User. Uses their login password
        to generate the encryption_key.

        see https://cryptography.io/en/latest/fernet/#using-passwords-with-fernet
        """

        # Generate a salt from hash and username
        salt = hashes.Hash(hashes.SHA256(), backend=default_backend())
        salt.update(self.user.username.encode())

        # Derive a key using PBKDF2-HMAC and the newly generated salt
        key_derivation_function = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt.finalize()[:16],  # can only finalize once; returns bytes; use 16 bytes
            iterations=1_000_000,  # Django recommendation of jan-2025
            backend=default_backend()
        )
        encryption_key = base64.urlsafe_b64encode(key_derivation_function.derive(password.encode()))

        # create and cache cipher
        self._cipher = Fernet(encryption_key)

    def clear_cipher(self):
        """Clear the cached Fernet instance (e.g., on logout)."""
        self._cipher = None

    def __str__(self):
        return f'{self.user.username} Profile'
