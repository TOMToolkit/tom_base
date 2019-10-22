import logging

from django.dispatch import receiver
from django.db.models.signals import post_save

from tom_common.hooks import run_hook
from tom_targets.models import Target

logger = logging.getLogger(__name__)


# Have post-save signal call hook in order to provide flexibility in the signal to hook into

@receiver(post_save, sender=Target)
def target_post_save(sender, **kwargs):
    print(kwargs['instance'].names)
    if not kwargs['created']:
        logger.info('Target post save hook: %s created: %s', kwargs['instance'], kwargs['created'])
        run_hook('target_post_save', target=kwargs['instance'], created=kwargs['created'])
