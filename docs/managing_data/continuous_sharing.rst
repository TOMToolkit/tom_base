Setting up Continuous Sharing
---------------------------------------

After setting up your TOM's `DATA_SHARING` destinations in your settings, you can set up individual Targets to share
their data automatically with a sharing destination as the data arrives in the TOM. Continuous Sharing is handled through
the `PersistentShare` model in the `tom_targets` module.


Permissions:
#############################

In order to setup continuous sharing, your user account must have the proper permissions, which means permissions to
add, view, and delete `PersistentShare` objects. A superuser account will have all permissions by default, but to give
permissions to another user, you can use code like this one time in the console:

.. code:: python

    from guardian.shortcuts import assign_perm

    # To assign the permission to a single user
    user = User.objects.get(username='myusername')
    assign_perm('tom_targets.view_persistentshare', user)
    assign_perm('tom_targets.add_persistentshare', user)
    assign_perm('tom_targets.delete_persistentshare', user)

    # To assign the permission to all users of a group
    group = Group.objects.get(name='mygroupname')
    assign_perm('tom_targets.view_persistentshare', group)
    assign_perm('tom_targets.add_persistentshare', group)
    assign_perm('tom_targets.delete_persistentshare', group)


The user must also have `change_target` permissions on the specific Target they are attempting to continuously share.


Managing Continuous Sharing:
*************************************************

There are a few ways to manage continuous sharing. First, you can navigate to any Target's share page `/targets/<target_pk>/share`
and you should see a tab for creating and viewing continuous sharing for that Target. You can also navigate to
`/targets/persistentshare/manage` to create and view all persistentshare objects you have permissions to see. There is also
a REST API for persistentshare objects that can be accessed at `/targets/persistentshare/`, which is used internally from the
manage pages.

If you have a custom target details page, you can integrate the controls for creating or managing continuous sharing using the
template partials below:

.. code:: html

    <h3>Continously Share data for Target <a href="{% url 'targets:detail' pk=target.id %}" title="Back">{{ target.name }}</a></h3>
    <div id='target-persistent-share-create'>
        {% create_persistent_share target %}
    </div>
    <h3>Manage Continuous Sharing for Target <a href="{% url 'targets:detail' pk=target.id %}"
          title="Back">{{ target.name }}</a></h3>
    <div id='target-persistent-share-table'>
        {% persistent_share_table target %}
    </div>

Note that setting up Continuous Sharing stores the destination from your `DATA_SHARING` settings. If you later change or remove that
destination then continuous shares using it will fail.

Also note that by default, continuous sharing will occur when a ReducedDatum is saved, or when the default `tom_base` `DataProcessor` is used
to load in a `DataProduct`. If you create your own `DataProcessor` subclass in your TOM, you must add the following lines to trigger continuous
sharing after you have bulk created the `ReducedDatums`:

.. code:: python

    from tom_targets.sharing import continuous_share_data
    # After all your logic to bulk_create ReducedDatums
    # Trigger any sharing you may have set to occur when new data comes in
    # Encapsulate this in a try/catch so sharing failure doesn't prevent dataproduct ingestion
    try:
        continuous_share_data(dp.target, reduced_datums)
    except Exception as e:
        logger.warning(f"Failed to share new dataproduct {dp.product_id}: {repr(e)}")
