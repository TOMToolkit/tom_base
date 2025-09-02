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

A Note About Saving Targets:
++++++++++++++++++++++++++++

The `Target.validate_unique()` method is not called when using the `Target.save()` or `Target.objects.create()`
methods to save a model. If you are creating targets in your TOM's custom code, you should call `validate_unique()`
manually to ensure that the target is unique, or use the `full_clean()` method to make sure that all of the individual
fields are valid as well. See the
`Django Docs <https://docs.djangoproject.com/en/5.0/ref/models/instances/#validating-objects>`__
for more information.

If you do wish to use your new match manager to validate or updated targets your code should look something like this:

.. code-block:: python
    :linenos:

    from django.core.exceptions import ValidationError
    from tom_targets.models import Target

    target = Target(name='My Target', ra=10.68458, dec=41.26906)
    try:
        target.validate_unique()  # or `target.full_clean()`
        target.save()
    except ValidationError as e:
        print(f'{target.name} not saved: {e}')

Customizing ``match_fuzzy_name``
++++++++++++++++++++++++++++++++

The ``match_fuzzy_name`` method is used to query the database for targets whose names ~kind of~ match the given string.
This method relies on ``simplify_name`` to create a processed version of the input string that can be compared to
similarly processed names and aliases in the database. By default, ``simplify_name`` removes capitalization, spaces,
dashes, underscores, and parentheses from the names, thus ``match_fuzzy_name`` will return targets whose names match
the given string ignoring these characters. (i.e. "My Target" will match both "my_target" and "(mY)tAr-GeT").

If you would like to customize the behavior of ``match_fuzzy_name``, you can override the ``simplify_name`` method in
your custom ``TargetMatchManager``. The following example demonstrates how to extend ``simplify_name`` to also consider
two names to be a match if they start with either 'AT' or 'SN'.


.. code-block:: python
    :caption: match_managers.py
    :linenos:
    :emphasize-lines: 14, 15

    from tom_targets.base_models import TargetMatchManager


    class CustomTargetMatchManager(TargetMatchManager):
        """
        Custom Match Manager for extending the built in TargetMatchManager.
        """

        def simplify_name(self, name):
            """
            Create a custom simplified name to be used for comparison in ``match_fuzzy_name``.
            """
            simple_name = super().simplify_name(name)  # Use the default simplification
            if simple_name.startswith('at'):
                simple_name = simple_name.replace('at', 'sn', 1)
            return simple_name


The highlighted lines could be replaced with any custom logic that you would like to use to determine if a target in
the database is a match for the name that is being checked. *NOTE* this will only actually be used by
``match_fuzzy_name``. If you are using ``match_exact_name`` these changes will not be used.