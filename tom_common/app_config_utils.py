"""TOMToolkit App developers can use these helper functions, typically from their AppConfig subclass.
"""

import logging

from django.apps import AppConfig
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


def auto_reencrypt_model_instances_for_user(
    app_config: AppConfig,
    user: 'User',  # noqa # type: ignore
    decoding_cipher: Fernet,
    encoding_cipher: Fernet,
    user_relation_field_name: str = 'user'
):
    """
    Automatically finds models in the app_config that inherit from EncryptableModelMixin
    and attempts to re-encrypt their fields for the given user.

    :param app_config: The AppConfig instance of the plugin app.
    :param user: The User whose data needs re-encryption.
    :param decoding_cipher: Fernet cipher to decrypt existing data.
    :param encoding_cipher: Fernet cipher to encrypt new data.
    :param user_relation_field_name: The name of the field on the plugin's model
                                     that links to the Django User model.
    """
    # Import models here, when the function is called, ensuring apps are ready.
    from django.contrib.auth.models import User  # noqa
    from tom_common.models import EncryptableModelMixin

    for model_class in app_config.get_models():
        if issubclass(model_class, EncryptableModelMixin):
            logger.debug(f"Found EncryptableModelMixin subclass: {model_class.__name__} in app {app_config.name}")
            if hasattr(model_class, user_relation_field_name):
                try:
                    # Handles OneToOneField or unique ForeignKey to User
                    instance = model_class.objects.get(**{user_relation_field_name: user})
                    instance.reencrypt_model_fields(decoding_cipher, encoding_cipher)
                except model_class.DoesNotExist:
                    logger.info(f"No {model_class.__name__} instance found for user {user.username} via field '{user_relation_field_name}'.")
                except model_class.MultipleObjectsReturned:
                    # Handles non-unique ForeignKey to User
                    logger.warning(f"Multiple {model_class.__name__} instances found for user {user.username} via field '{user_relation_field_name}'. Re-encrypting all.")
                    instances = model_class.objects.filter(**{user_relation_field_name: user})
                    for instance in instances:
                        instance.reencrypt_model_fields(decoding_cipher, encoding_cipher)
                except Exception as e:
                    logger.error(f"Error processing model {model_class.__name__} for re-encryption for user {user.username}: {e}")
            else:
                logger.warning(f"Model {model_class.__name__} is Encryptable but does not have a direct '{user_relation_field_name}' attribute. Cannot automatically fetch instance for user {user.username} for re-encryption.")