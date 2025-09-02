from django.dispatch import receiver
from django.db.models.signals import post_save, post_delete
from guardian.utils import clean_orphan_obj_perms

from tom_dataproducts.models import ReducedDatum
from tom_targets.sharing import continuous_share_data
from tom_targets.models import Target


@receiver(post_save, sender=ReducedDatum)
def cb_reduceddatum_post_save(sender, instance, *args, **kwargs):
    # When a new ReducedDatum is created or updated, check for any persistentshare instances on that target
    # and if they exist, attempt to share the new data
    target = instance.target
    continuous_share_data(target, reduced_datums=[instance])


@receiver(post_delete, sender=Target)
def cb_target_post_delete(sender, instance, *args, **kwargs):
    # When a Target is deleted, clean up orphaned permissions.
    # Note that this removes ALL orphaned permissions, not just those
    # associated with this target.
    clean_orphan_obj_perms()
