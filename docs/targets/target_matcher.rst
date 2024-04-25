Customizing a Target Matcher
----------------------------

The role of the ``TargetMatchManager`` is to return a queryset of targets that match a given set of parameters.
By default, the TOM Toolkit includes a ``TargetMatchManager`` that contains several methods that are detailed
in :doc:`Target: Models <../api/tom_targets/models>`. These functions can be modified or replaced by a user to
alter the conditions under which a target is considered a match.

Using the TargetMatchManager
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``TargetMatchManager`` is a django model manager defined as ``Target.matches``.
Django model managers are described in more detail in the `Django Docs <https://docs.djangoproject.com/en/4.2/topics/db/managers/>`_.

You can use the ``TargetMatchManager`` to return a queryset of targets that satisfy a cone search with the following:

.. code:: python

    from tom_targets.models import Target

    # Define the center of the cone search
    ra = 10.68458  # Degrees
    dec = 41.26906  # Degrees
    radius = 12   # Arcseconds

    # Get the queryset of targets that match the cone search
    targets = Target.matches.match_cone_search(ra, dec, radius)

Extending the TargetMatchManager
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To start, find the ``MATCH_MANAGERS`` definition in your ``settings.py``:

.. code:: python

   # Define MATCH_MANAGERS here. This is a dictionary that contains a dotted module path to the desired match manager
   # for a given model.
   # For example:
   # MATCH_MANAGERS = {
   #    "Target": "custom_code.match_managers.CustomTargetMatchManager"
   # }
   MATCH_MANAGERS = {}

Add the path to your custom ``TargetMatchManager`` to the "Target" key of the MATCH_MANAGERS dictionary as shown in the
example.

Once you have defined your custom ``TargetMatchManager`` in ``settings.py``, you can need to create the custom
``TargetMatchManager`` in your project. We recommend you do this inside your project's ``custom_code`` app, but can be
placed anywhere.

The ``TargetMatchManager`` can be extended to include additional methods or to override any of the default methods
described in :doc:`Target: Models <../api/tom_targets/models>`. The following code provides an example of a custom
``TargetMatchManager`` that checks for exact name matches instead of the default fuzzy matches. This would change the
default behavior for several parts of the TOM Toolkit that endeavor to determine if a target or alias is unique based on
its name.

.. code-block:: python
    :caption: match_managers.py
    :linenos:
    :emphasize-lines: 15

    from tom_targets.base_models import TargetMatchManager


    class CustomTargetMatchManager(TargetMatchManager):
        """
        Custom Match Manager for extending the built in TargetMatchManager.
        """

        def match_name(self, name):
            """
            Returns a queryset exactly matching name that is received
            :param name: The string against which target names will be matched.
            :return: queryset containing matching Target(s).
            """
            queryset = self.match_exact_name(name)
            return queryset


.. note::
    The default behavior for ``match_name`` is to perform a "fuzzy match". This can be computationally expensive
    for large databases. If you have experienced this issue, you can override the ``match_name`` method to only
    return exact matches using the above example.


Next we have another example of a ``TargetMatchManager`` that extends the ``match_target`` matcher to not only include name
matches but also considers any target with an RA and DEC less than 2" away from the given target to be a match for the
target.

.. code-block:: python
    :caption: match_managers.py
    :linenos:
    :emphasize-lines: 17, 18

    from tom_targets.base_models import TargetMatchManager


    class CustomTargetMatchManager(TargetMatchManager):
        """
        Custom Match Manager for extending the built in TargetMatchManager.
        """

        def match_target(self, target, *args, **kwargs):
            """
            Returns a queryset containing any targets that are both a fuzzy match and within 2 arcsec of
            the target that is received
            :param target: The target object to be checked.
            :return: queryset containing matching Target(s).
            """
            queryset = super().match_target(target, *args, **kwargs)
            radius = 2  # Arcseconds
            cone_search_queryset = self.match_cone_search(target.ra, target.dec, radius)
            return queryset | cone_search_queryset


The highlighted lines could be replaced with any custom logic that you would like to use to determine if a target in
the database is a match for the target that is being checked. This is extremely powerful since this code is ultimately used
by ``Target.validate_unique()`` to determine if a new target can be saved to the database, and thus prevent your TOM
from accidentally ingesting duplicate targets.

Your ``MatchManager`` should subclass the ``base_model.TargetMatchManager`` which will contain both a ``match_target``
method and a ``match_name`` method, both of which should return a queryset. These methods can be modified or
extended, as in the above example, as needed.

