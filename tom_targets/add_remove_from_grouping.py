from .filters import TargetFilter
from .models import Target, TargetList
from django.contrib import messages
from django.http import QueryDict

def add_all_to_grouping(filter_data, grouping_object, request): 
    success_targets = []
    warning_targets = [] #targets that are already in the grouping
    failure_targets = []
    try:
        target_queryset = TargetFilter(request=request, data=filter_data, queryset=Target.objects.all()).qs
    except Exception as e:
        message.error(request, "Error with filter parameters. No target(s) were added to group '{}'.".format(grouping_object.name))
        return
    for target_object in target_queryset:
        try:
            if not request.user.has_perm('tom_targets.view_target', target_object):
                failure_targets.append((target_object.identifier, 'Permission denied.',))
            elif target_object in grouping_object.targets.all(): 
                warning_targets.append(target_object.identifier)
            else:
                grouping_object.targets.add(target_object)
                success_targets.append(target_object.identifier)
        except Exception as e:
            failure_targets.append((target_object.pk, e,))
    messages.success(request, "{} target(s) successfully added to group '{}'.".format(len(success_targets), grouping_object.name))
    if warning_targets:
        messages.warning(request, "{} target(s) already in group '{}': {}".format(len(warning_targets), grouping_object.name, ', '.join(warning_targets)))
    for failure_target in failure_targets:
        messages.error(request, "Failed to add target with id={} to group '{}'; {}".format(failure_target[0], grouping_object.name, failure_target[1]))
    

def add_selected_to_grouping(targets_ids, grouping_object, request):
    success_targets = []
    warning_targets = []
    failure_targets = []
    for target_id in targets_ids:
        try:
            target_object = Target.objects.get(pk=target_id)
            if not request.user.has_perm('tom_targets.view_target', target_object):
                failure_targets.append((target_object.identifier, 'Permission denied.',))
            elif target_object in grouping_object.targets.all(): 
                warning_targets.append(target_object.identifier)
            else:
                grouping_object.targets.add(target_object)
                success_targets.append(target_object.identifier)
        except Exception as e:
            failure_targets.append((target_object.pk, e,))
    messages.success(request, "{} target(s) successfully added to group '{}'.".format(len(success_targets), grouping_object.name))
    if warning_targets:
        messages.warning(request, "{} target(s) already in group '{}': {}".format(len(warning_targets), grouping_object.name, ', '.join(warning_targets)))
    for failure_target in failure_targets:
        messages.error(request, "Failed to add target with id={} to group '{}'; {}".format(failure_target[0], grouping_object.name, failure_target[1]))


def remove_all_from_grouping(filter_data, grouping_object, request): 
    success_targets = []
    warning_targets = []
    failure_targets = []
    try:
        target_queryset = TargetFilter(request=request, data=filter_data, queryset=Target.objects.all()).qs
    except Exception as e:
        message.error(request, "Error with filter parameters. No target(s) were removed from group '{}'.".format(grouping_object.name))
        return
    for target_object in target_queryset:
        try:
            if not request.user.has_perm('tom_targets.view_target', target_object):
                failure_targets.append((target_object.identifier, 'Permission denied.',))
            elif not target_object in grouping_object.targets.all(): 
                warning_targets.append(target_object.identifier)
            else:
                grouping_object.targets.remove(target_object)
                success_targets.append(target_object.identifier)
        except Exception as e:
            failure_targets.append({'id':target_id, 'error':e})
    messages.success(request, "{} target(s) successfully removed from group '{}'.".format(len(success_targets), grouping_object.name))
    if warning_targets:
        messages.warning(request, "{} target(s) not in group '{}': {}".format(len(warning_targets), grouping_object.name, ', '.join(warning_targets)))
    for failure_target in failure_targets:
        messages.error(request, "Failed to remove target with id={} from group '{}'; {}".format(failure_target['id'], grouping_object.name, failure_target['error']))
    

def remove_selected_from_grouping(targets_ids, grouping_object, request):
    success_targets = []
    warning_targets = []
    failure_targets = []
    for target_id in targets_ids:
        try:
            target_object = Target.objects.get(pk=target_id)
            if not request.user.has_perm('tom_targets.view_target', target_object):
                failure_targets.append((target_object.identifier, 'Permission denied.',))
            elif not target_object in grouping_object.targets.all(): 
                warning_targets.append(target_object.identifier)
            else:
                grouping_object.targets.remove(target_object)
                success_targets.append(target_object.identifier)
        except Exception as e:
            failure_targets.append({'id':target_id, 'error':e})
    messages.success(request, "{} target(s) successfully removed from group '{}'.".format(len(success_targets), grouping_object.name))
    if warning_targets:
        messages.warning(request, "{} target(s) not in group '{}': {}".format(len(warning_targets), grouping_object.name, ', '.join(warning_targets)))
    for failure_target in failure_targets:
        print(failure_target)
        messages.error(request, "Failed to remove target with id={} from group '{}'; {}".format(failure_target['id'], grouping_object.name, failure_target['error']))

def add_remove_from_grouping(request, query_string):
    grouping_id = request.POST.get('grouping')
    filter_data = QueryDict(query_string)
    try:
        grouping_object = TargetList.objects.get(pk=grouping_id)
    except Exception as e:
        messages.error(request, 'Cannot find the target group with id={}; {}'.format(grouping_id, e))
        return 
    if not request.user.has_perm('tom_targets.view_targetlist', grouping_object):
        messages.error(request, 'Permission denied.')
        return 

    if 'add' in request.POST:
        if request.POST.get('isSelectAll') == 'True':
            add_all_to_grouping(filter_data, grouping_object, request)
        else:
            targets_ids = request.POST.getlist('selected-target')
            add_selected_to_grouping(targets_ids, grouping_object, request)
    if 'remove' in request.POST:
        if request.POST.get('isSelectAll') == 'True':
            remove_all_from_grouping(filter_data, grouping_object, request)
        else:
            targets_ids = request.POST.getlist('selected-target')
            remove_selected_from_grouping(targets_ids, grouping_object, request)
