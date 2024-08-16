from django.contrib import messages
from tom_targets.models import TargetName, TargetExtra
from tom_dataproducts.models import ReducedDatum, DataProduct
from tom_observations.models import ObservationRecord


def merge_error_message(request):
    """
    This warns the user if they are selecting too little or too many targets to merge.
    Will not allow user to continue to merge page unless two targets are selected.
    """
    messages.warning(request, "Please select two targets to merge!")


def target_merge(primary_target, secondary_target):
    """
    Merge Primary target and Secondary target into one target. Attributes primary_target does not have,
    but secondary_target does have, will get merged into primary_target. After attributes merged,
    secondary_target is deleted.

    :param primary_target: Target object which holds all the primary_target attributes
    :type target: tom_targets.models.Target

    :param secondary_target: Target object which holds all the secondary_target attributes
    :type target: tom_targets.models.Target

    returns: primary_target
    """

    model_fields = primary_target._meta.fields
    # loops through target attributes. If attribute missing from primary target
    # and secondary target has the attribute, the attribute gets merged into Primary target
    for field in model_fields:
        if getattr(primary_target, field.name, None) is None\
                and getattr(secondary_target, field.name, None) is not None:
            setattr(primary_target, field.name, getattr(secondary_target, field.name, None))
            primary_target.save()

    new_name = TargetName(target=primary_target, name=secondary_target.name)
    new_name.save()

    merge_aliases = secondary_target.aliases.all()
    # Secondary target name and aliases all become aliases in the Primary target.

    for alias in merge_aliases:
        alias_hold = alias.name
        alias.delete()
        new_name = TargetName(target=primary_target, name=alias_hold)
        new_name.save()

    # Call all TargetLists associated with the secondary_target
    st_lists = secondary_target.targetlist_set.all()
    for targetlist in st_lists:
        targetlist.targets.add(primary_target)

    # take secondary_target dataproducts and save them as primary_target dataproducts
    st_dataproducts = DataProduct.objects.filter(target=secondary_target)
    for dataproduct in st_dataproducts:
        dataproduct.target = primary_target
        dataproduct.save()

    # take secondary_target reduceddatums and save them as primary_target reduceddatums
    st_reduceddatums = ReducedDatum.objects.filter(target=secondary_target)
    for reduceddatum in st_reduceddatums:
        reduceddatum.target = primary_target
        reduceddatum.save()

    #  TODO: skip reduceddatums with values that are identical (do this with an if statement)
    #  access value with reduceddatum.value

    # take secondary target extras without repeated keys and save them as primary target extras
    pt_targetextra_keys = list(TargetExtra.objects.filter(target=primary_target).values_list("key", flat=True))
    st_targetextras = TargetExtra.objects.filter(target=secondary_target)
    for targetextra in st_targetextras:
        if targetextra.key not in pt_targetextra_keys:
            targetextra.target = primary_target
            targetextra.save()

    # take secondary_target observationrecords and save them as primary_target observationrecords
    st_observationrecords = ObservationRecord.objects.filter(target=secondary_target)
    for observationrecord in st_observationrecords:
        observationrecord.target = primary_target
        observationrecord.save()

    secondary_target.delete()

    return primary_target
