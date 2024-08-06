from django.contrib import messages
from tom_targets.models import TargetName

def merge_error_message(request):
    messages.warning(request, "Please select two targets to merge!")

def target_merge(primary_target, secondary_target):
    """
    """
   
    model_fields = primary_target._meta.fields
    for field in model_fields:
        if  getattr(primary_target, field.name, None) is None and getattr(secondary_target, field.name, None) is not None:
            setattr(primary_target, field.name, getattr(secondary_target, field.name, None))
            primary_target.save()

    new_name = TargetName(target=primary_target, name=secondary_target.name)
    new_name.save()

    secondary_target.delete()

    return primary_target