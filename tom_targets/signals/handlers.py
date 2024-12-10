from django.dispatch import receiver
from django.db.models.signals import post_save

from tom_dataproducts.models import ReducedDatum
from tom_dataproducts.sharing import share_data_with_destination
from tom_targets.models import PersistentShare


@receiver(post_save, sender=ReducedDatum)
def cb_dataproduct_post_save(sender, instance, *args, **kwargs):
    # When a new dataproduct is created or updated, check for any persistentshare instances on that target
    # and if they exist, attempt to share the new data
    target = instance.target
    persistentshares = PersistentShare.objects.filter(target=target)
    for persistentshare in persistentshares:
        share_destination = persistentshare.destination
        share_data_with_destination(share_destination, instance)
