Targets
=======

The ``Target``, along with the associated ``TargetList``, ``TargetExtra``, and ``TargetName``, are the core models of the
TOM Toolkit. The ``Target`` defines the concept of an astronomical target through a number of parameters. The ``Target``
object is then used throughout the TOM to reference all the
information a user or app needs to know about a target.  As astrophysical objects are often identified in multiple catalogs,
each ``Target`` is associated with one or more ``TargetName``s.

More information on Targets can be found using the following pages:

:doc:`Target Models </api/tom_targets/models>` - Take a look at the available properties for a ``Target`` and its associated models.

:doc:`Target Views </api/tom_targets/views>` - Familiarize yourself with the available Target Views.

:doc:`Target Lists </api/tom_targets/groups>` - Check out the functions for operating on Target Lists/Target Groups.


Customizing the BaseTarget
--------------------------

Although almost all astrophysical targets share some descriptive parameters - such as RA, Dec or orbital parameters -
the Toolkit recognises that each science case has a specific set of relevant parameters.  For example, for some science
goals, a ``Target`` may have a measured period, while this may not be appropriate for an aperiodic object.

For this reason, the Toolkit provides a ``BaseTarget`` class which supports both sidereal and non-sidereal celestial objects.
By default, this is used to create the ``Target`` model when a TOM is created.
However, this class is designed to be extended by users to add fields relevant to their science.  See
:doc:`Adding Custom Target Fields <target_fields>` to learn how to add custom fields to your TOM Targets.

Crossmatching Targets
---------------------

It is often useful to compare a target with those already in the TOM, especially to avoid duplicating targets.
By default, matching is performed on ``TargetName``, but the TOM includes functions to match on position as well.
If you need to compare targets using different parameters, :doc:`Customizing a Target Matcher <target_matcher>`
describes how to add a custom match function.

TargetLists
-----------

By default, all targets in the TOM are treated as a single collection, which can be viewed as a table and on an
interactive skymap by navigating to the Targets view.
The columns presented in the target list table can be customized - see :doc:`Customizing the Target List Table <target_table>`
for more information.

Targets can be collected into user-created lists for convenience.

Target and TargetList Sharing
-----------------------------

Individual targets and their associated data can be shared directly with another TOM, with the TOM administrator's
permission.  Sets of targets can also be shared.  See :doc:`TOM Direct Sharing </managing_data/tom_direct_sharing>`
to learn how to configure the TOMs to allow this.