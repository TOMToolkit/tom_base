The Permissions System
======================

The permissions system is built on top of
`django-guardian <https://django-guardian.readthedocs.io/en/stable/>`_. It has been
kept as simple as possible, but TOM developers may extend the capabilities if
needed.

The TOM Toolkit provides a permissions system that can be used in two different modes. The mode is controlled by the
``TARGET_PERMISSIONS_ONLY`` boolean in ``settings.py``.


First Mode -- Permissions on Targets and Observation Records
------------------------------------------------------------


The first mode limits the targets that a user or a group of users can access. This may be helpful if you have many
users in your TOM but would like to keep some targets proprietary. In addition, users are limited to accessing only the
observation records and data products associated with the targets for which they have permission to view.

Permissions are enforced through groups. Groups can be created and managed by any
PI in the TOM, via the users page. To add a group, simply use the "Add Group"
button found at the top of the groups table:


.. image:: /_static/permissions_doc/addgroup.png

![](/_static/permissions_doc/addgroup.png)

Modifying a group will allow you to change it's name and add/remove users.

When a user adds or modifies a target, they are able to choose the groups to
assign to the target:

.. image:: /_static/permissions_doc/targetgroups.png

![](/_static/permissions_doc/targetgroups.png)


By default the target will be assigned to all groups the user belongs to.

There is a special group, "Public". By default, all users belong to the Public
group, so all targets assigned to it would be accessible by anyone. The PI does
have the ability to remove users for the Public group, however.


Second Mode -- Permissions on most objects
------------------------------------------

The second permissions mode is an expanded version of the first. Observation records and data products can be restricted
to certain groups, and children of those objects will have the same restrictions--that is, all data products of an
observation record will share its permissions, and all reduced datums of a data product will share its permissions.


A note about toggling ``TARGET_PERMISSIONS_ONLY``
-------------------------------------------------

It must be noted that while ``TARGET_PERMISSIONS_ONLY`` is set to ``True``, no permissions will be set on any objects other
than targets. This means that if your TOM is used with ``TARGET_PERMISSIONS_ONLY``, and ``TARGET_PERMISSIONS_ONLY`` is
disabled after the fact, all permissions will need to be configured manually.


Manual permissions modification
-------------------------------

If you want to disable ``TARGET_PERMISSIONS_ONLY`` after adding any data, you'll need to do so on your own. We encourage you to read the documention on django-guardian linked above, but here's an example of a bulk permissions assignment for
a target:

.. code-block:: python

    >>> from django.contrib.auth.models import Group, User
    >>> from guardian.shortcuts import assign_perm
    >>> from tom_targets.models import Target
    >>> user = User.objects.filter(username='jaire_alexander').first()
    >>> groups = user.groups.all()
    >>> targets = Target.objects.all()
    >>> for group in groups:
    ...  assign_perm('tom_targets.view_target', group, targets)
    ...  assign_perm('tom_targets.change_target', group, targets)
    ...  assign_perm('tom_targets.delete_target', group, targets)

The above code will allow all users in the groups that the example user belongs to to view, modify, and delete all targets. This example can be expanded to the other model-related permissions in the TOM. Below is a brief list of the permissions-enabled models with their permission names:

``Targets``:

* ``tom_targets.view_target``
* ``tom_targets.change_target``
* ``tom_targets.delete_target``

``TargetLists``:

* ``tom_targets.view_targetlist``
* ``tom_targets.delete_targetlist``

``ObservationRecords``:

* ``tom_observations.view_observationrecord``

``ObservationGroups``:

* ``tom_observations.view_observationgroup``

``DataProducts``:

* ``tom_dataproducts.view_dataproduct``
* ``tom_dataproducts.delete_dataproduct``

``ReducedDatum``:

* ``tom_dataproducts.view_reduceddatum``