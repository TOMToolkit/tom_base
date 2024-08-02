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
    for each in model_fields:
        print(each)
    different_fields = filter(lambda field: getattr(primary_target,field,None) != getattr(secondary_target,field,None),model_fields)
    print(list(different_fields))
    print("hi hi hi")
    print(primary_target)
    print("hello")
    print("i did it!!!!")

    return primary_target