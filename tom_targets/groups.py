from .filters import TargetFilter
from .models import Target
from django.contrib import messages


def add_all_to_grouping(filter_data, grouping_object, request):
    """
    Adds all targets displayed by a particular filter to a ``TargetList``. Successes, warnings, and errors result in
    messages being added to the request with the appropriate message level.

    :param filter_data: target filter data passed to the calling view
    :type filter_data: django.http.QueryDict

    :param grouping_object: ``TargetList`` to add targets to
    :type grouping_object: TargetList

    :param request: request object passed to the calling view
    :type request: HTTPRequest
    """
    success_targets = []
    warning_targets = []  # targets that are already in the grouping
    failure_targets = []
    try:
        target_queryset = TargetFilter(request=request, data=filter_data, queryset=Target.objects.all()).qs
    except Exception:
        messages.error(request, "Error with filter parameters. No target(s) were added to group '{}'."
                                .format(grouping_object.name))
        return
    for target_object in target_queryset:
        try:
            if not request.user.has_perm('tom_targets.change_target', target_object):
                failure_targets.append((target_object.name, 'Permission denied.',))
            elif target_object in grouping_object.targets.all():
                warning_targets.append(target_object.name)
            else:
                grouping_object.targets.add(target_object)
                success_targets.append(target_object.name)
        except Exception as e:
            failure_targets.append((target_object.pk, e,))
    messages.success(request, "{} target(s) successfully added to group '{}'."
                              .format(len(success_targets), grouping_object.name))
    if warning_targets:
        messages.warning(request, "{} target(s) already in group '{}': {}"
                                  .format(len(warning_targets), grouping_object.name, ', '.join(warning_targets)))
    for failure_target in failure_targets:
        messages.error(request, "Failed to add target with id={} to group '{}'; {}"
                                .format(failure_target[0], grouping_object.name, failure_target[1]))


def add_selected_to_grouping(targets_ids, grouping_object, request):
    """
    Adds all selected targets to a ``TargetList``. Successes, warnings, and errors result in messages being added to the
    request with the appropriate message level.

    :param targets_ids: list of selected targets
    :type targets_ids: list

    :param grouping_object: ``TargetList`` to add targets to
    :type grouping_object: TargetList

    :param request: request object passed to the calling view
    :type request: HTTPRequest
    """
    success_targets = []
    warning_targets = []
    failure_targets = []
    for target_id in targets_ids:
        try:
            target_object = Target.objects.get(pk=target_id)
            if not request.user.has_perm('tom_targets.change_target', target_object):
                failure_targets.append((target_object.name, 'Permission denied.',))
            elif target_object in grouping_object.targets.all():
                warning_targets.append(target_object.name)
            else:
                grouping_object.targets.add(target_object)
                success_targets.append(target_object.name)
        except Exception as e:
            failure_targets.append((target_object.pk, e,))
    messages.success(request, "{} target(s) successfully added to group '{}'."
                              .format(len(success_targets), grouping_object.name))
    if warning_targets:
        messages.warning(request, "{} target(s) already in group '{}': {}"
                                  .format(len(warning_targets), grouping_object.name, ', '.join(warning_targets)))
    for failure_target in failure_targets:
        messages.error(request, "Failed to add target with id={} to group '{}'; {}"
                                .format(failure_target[0], grouping_object.name, failure_target[1]))


def remove_all_from_grouping(filter_data, grouping_object, request):
    """
    Removes all targets displayed by a particular filter from a ``TargetList``. Successes, warnings, and errors result
    in messages being added to the request with the appropriate message level.

    :param filter_data: target filter data passed to the calling view
    :type filter_data: django.http.QueryDict

    :param grouping_object: ``TargetList`` to remove targets from
    :type grouping_object: TargetList

    :param request: request object passed to the calling view
    :type request: HTTPRequest
    """
    success_targets = []
    warning_targets = []
    failure_targets = []
    try:
        target_queryset = TargetFilter(request=request, data=filter_data, queryset=Target.objects.all()).qs
    except Exception:
        messages.error(request, "Error with filter parameters. No target(s) were removed from group '{}'."
                                .format(grouping_object.name))
        return
    for target_object in target_queryset:
        try:
            if not request.user.has_perm('tom_targets.change_target', target_object):
                failure_targets.append((target_object.name, 'Permission denied.',))
            elif target_object not in grouping_object.targets.all():
                warning_targets.append(target_object.name)
            else:
                grouping_object.targets.remove(target_object)
                success_targets.append(target_object.name)
        except Exception as e:
            failure_targets.append({'name': target_object.name, 'error': e})
    messages.success(request, "{} target(s) successfully removed from group '{}'."
                              .format(len(success_targets), grouping_object.name))
    if warning_targets:
        messages.warning(request, "{} target(s) not in group '{}': {}"
                                  .format(len(warning_targets), grouping_object.name, ', '.join(warning_targets)))
    for failure_target in failure_targets:
        messages.error(request, "Failed to remove target with id={} from group '{}'; {}"
                                .format(failure_target['id'], grouping_object.name, failure_target['error']))


def remove_selected_from_grouping(targets_ids, grouping_object, request):
    """
    Removes all targets displayed by a particular filter from a ``TargetList``. Successes, warnings, and errors result
    in messages being added to the request with the appropriate message level.

    :param targets_ids: list of selected targets
    :type targets_ids: list

    :param grouping_object: ``TargetList`` to remove targets from
    :type grouping_object: TargetList

    :param request: request object passed to the calling view
    :type request: HTTPRequest
    """
    success_targets = []
    warning_targets = []
    failure_targets = []
    for target_id in targets_ids:
        try:
            target_object = Target.objects.get(pk=target_id)
            if not request.user.has_perm('tom_targets.change_target', target_object):
                failure_targets.append((target_object.name, 'Permission denied.',))
            elif target_object not in grouping_object.targets.all():
                warning_targets.append(target_object.name)
            else:
                grouping_object.targets.remove(target_object)
                success_targets.append(target_object.name)
        except Exception as e:
            failure_targets.append({'id': target_id, 'error': e})
    messages.success(request, "{} target(s) successfully removed from group '{}'."
                              .format(len(success_targets), grouping_object.name))
    if warning_targets:
        messages.warning(request, "{} target(s) not in group '{}': {}"
                                  .format(len(warning_targets), grouping_object.name, ', '.join(warning_targets)))
    for failure_target in failure_targets:
        messages.error(request, "Failed to remove target with id={} from group '{}'; {}"
                                .format(failure_target['id'], grouping_object.name, failure_target['error']))


def move_all_to_grouping(filter_data, grouping_object, request):
    """
    Moves all targets displayed by a particular filter to a ``TargetList`` by removing all previous gropupings
    and then adding them to the supplied grouping_object.
    Successes, warnings, and errors result
    in messages being added to the request with the appropriate message level.

    :param filter_data: target filter data passed to the calling view
    :type filter_data: django.http.QueryDict

    :param grouping_object: ``TargetList`` to add targets to
    :type grouping_object: TargetList

    :param request: request object passed to the calling view
    :type request: HTTPRequest
    """
    success_targets = []
    warning_targets = []
    failure_targets = []
    try:
        target_queryset = TargetFilter(request=request, data=filter_data, queryset=Target.objects.all()).qs
    except Exception:
        messages.error(request, "Error with filter parameters. No target(s) were moved to group '{}'."
                                .format(grouping_object.name))
        return
    for target_object in target_queryset:
        try:
            if not request.user.has_perm('tom_targets.change_target', target_object):
                failure_targets.append((target_object.name, 'Permission denied.',))
            elif target_object in grouping_object.targets.all():
                warning_targets.append(target_object.name)
            else:
                target_object.targetlist_set.clear()
                grouping_object.targets.add(target_object)
                success_targets.append(target_object.name)
        except Exception as e:
            failure_targets.append({'name': target_object.name, 'error': e})
    messages.success(request, "{} target(s) successfully moved to group '{}'."
                              .format(len(success_targets), grouping_object.name))
    if warning_targets:
        messages.warning(request, "{} target(s) already in group '{}': {}"
                                  .format(len(warning_targets), grouping_object.name, ', '.join(warning_targets)))
    for failure_target in failure_targets:
        messages.error(request, "Failed to move target with id={} to group '{}'; {}"
                                .format(failure_target['id'], grouping_object.name, failure_target['error']))


def move_selected_to_grouping(targets_ids, grouping_object, request):
    """
    Moves all selected targets to a ``TargetList`` by removing them from their previous groupings
    and then adding them to the supplied grouping_object.
    Successes, warnings, and errors result in messages being added to the
    request with the appropriate message level.

    :param targets_ids: list of selected targets
    :type targets_ids: list

    :param grouping_object: ``TargetList`` to add targets to
    :type grouping_object: TargetList

    :param request: request object passed to the calling view
    :type request: HTTPRequest
    """
    success_targets = []
    warning_targets = []
    failure_targets = []
    for target_id in targets_ids:
        try:
            target_object = Target.objects.get(pk=target_id)
            if not request.user.has_perm('tom_targets.change_target', target_object):
                failure_targets.append((target_object.name, 'Permission denied.',))
            elif target_object in grouping_object.targets.all():
                warning_targets.append(target_object.name)
            else:
                target_object.targetlist_set.clear()
                grouping_object.targets.add(target_object)
                success_targets.append(target_object.name)
        except Exception as e:
            failure_targets.append((target_id, e,))
    messages.success(request, "{} target(s) successfully moved to group '{}'."
                              .format(len(success_targets), grouping_object.name))
    if warning_targets:
        messages.warning(request, "{} target(s) already in group '{}': {}"
                                  .format(len(warning_targets), grouping_object.name, ', '.join(warning_targets)))
    for failure_target in failure_targets:
        messages.error(request, "Failed to move target with id={} to group '{}'; {}"
                                .format(failure_target[0], grouping_object.name, failure_target[1]))
