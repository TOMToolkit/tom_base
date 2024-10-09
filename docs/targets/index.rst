Targets
=======

.. toctree::
  :maxdepth: 2
  :hidden:

  target_fields
  target_matcher
  ../api/tom_targets/models
  ../api/tom_targets/views
  ../api/tom_targets/groups


The ``Target``, along with the associated ``TargetList``, ``TargetExtra``, and ``TargetName``, are the core models of the 
TOM Toolkit. The ``Target`` defines the concept of an astronomical target through a number of parameters. This
object is then used throughout the TOM to reference all the information a user or app needs to know about a target.
More information on Targets can be found using the following pages:

:doc:`Adding Custom Target Fields <target_fields>` - Learn how to add custom fields to your TOM Targets if the
defaults do not suffice.

:doc:`Customizing a Target Matcher <target_matcher>` - Learn how to replace or modify the TargetMatchManager if more
options are needed.

:doc:`Target Models <../api/tom_targets/models>` - Take a look at the available properties for a ``Target`` and its associated models.

:doc:`Target Views <../api/tom_targets/views>` - Familiarize yourself with the available Target Views.

:doc:`Target Lists <../api/tom_targets/groups>` - Check out the functions for operating on Target Lists/Target Groups.
