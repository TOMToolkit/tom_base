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
    targets = Target.matches.check_for_nearby_match(ra, dec, radius)

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

The following code provides an example of a custom ``TargetMatchManager`` that checks for exact name matches and
requires that a target must have an RA and DEC more than 2" away from any other target in the database to be considered
unique:

.. code-block:: python
    :caption: match_managers.py
    :linenos:

    from tom_targets.base_models import TargetMatchManager


    class CustomTargetMatchManager(TargetMatchManager):
        """
        Custom Match Manager for extending the built in TargetMatchManager.
        """

        def check_unique(self, target, *args, **kwargs):
            """
            Returns a queryset containing any targets that are both a fuzzy match and within 2 arcsec of
            the target that is received
            :param target: The target object to be checked.
            :return: queryset containing matching Target(s).
            """
            queryset = super().check_unique(target, *args, **kwargs)
            radius = 2
            cone_search_queryset = self.check_for_nearby_match(target.ra, target.dec, radius)
            return queryset | cone_search_queryset

        def get_name_match(self, name):
            """
            Returns a queryset exactly matching name that is received
            :param name: The string against which target names will be matched.
            :return: queryset containing matching Target(s).
            """
            queryset = self.check_for_exact_name_match(name)
            return queryset

Your ``MatchManager`` should extend the ``base_model.TargetMatchManager`` which will contain both a ``check_unique``
method and a ``get_name_match`` method, both of which should return a queryset. These methods can be modified or
extended, as in the above example, as needed.

.. note::
    The default behavior for ``get_name_match`` is to perform a "fuzzy match". This can be computationally expensive
    for large databases. If you have experienced this issue, you can override the ``get_name_match`` method to only
    return exact matches using the above example.
