from django.contrib import messages


def merge_error_message(request):
    messages.warning(request, "Please select two targets to merge!")


def target_merge(primary_target, secondary_target):
    """
    """
    print("+++++++++++++++++++++++++++++++++++++++++++++++++++++")
    # for each in primary_target._meta.fields:
    #     print(each)

    model_fields = primary_target._meta.fields
    for field in model_fields:
        print(f"the field is {field}")
        if  getattr(primary_target, field.name, None) is None and getattr(secondary_target, field.name, None) is not None:
            setattr(primary_target, field.name, getattr(secondary_target, field.name, None))
            primary_target.save()
    different_fields = filter(lambda field: getattr(primary_target, field.name, None) != getattr(secondary_target, field.name, None), model_fields)
    # new_fields = filter(lambda field: getattr(primary_target,field.name, None) == getattr(secondary_target,field.name, None), model_fields)
    print(list(different_fields))
    print("hi hi hi")
    print(primary_target)
    print("hello")
    print("i did it!!!!")
    # print(list(new_fields))

    return primary_target
