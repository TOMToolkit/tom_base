from django.dispatch import receiver
from django.db.models.signals import post_save

from tom_dataproducts.models import ReducedDatum
from tom_targets.sharing import continuous_share_data


@receiver(post_save, sender=ReducedDatum)
def cb_reduceddatum_post_save(sender, instance, *args, **kwargs):
    # When a new ReducedDatum is created or updated, check for any persistentshare instances on that target
    # and if they exist, attempt to share the new data
    target = instance.target
    continuous_share_data(target, reduced_datums=[instance])
