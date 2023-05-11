Adding Custom Target Matcher
----------------------------

The role of the ``TargetMatchManager`` is to return a queryset of targets that match a given set of parameters.
By default, the TOM Toolkit includes a ``TargetMatchManager`` that contains a ``check_for_fuzzy_match`` function that
will return a queryset of ``TargetNames`` that are "similar" to a given string. This function will check for
case-insensitive aliases while ignoring spaces, dashes, underscore, and parentheses. This function is used during
``validate_unique`` when the target is saved to ensure that redundant targets are not added.

Under certain circumstances a user may wish to modify or add to this behavior.

Using the TargetMatchManager
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``TargetMatchManager`` is a django model manager defined as ``Target.matches``.
Django model managers are described in more detail in the `Django Docs <https://docs.djangoproject.com/en/4.2/topics/db/managers/>`_.

Overriding the TargetMatchManager
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To start, find the ``MATCH_MANAGERS`` definition in your ``settings.py``:

.. code:: python

   # Define MATCH_MANAGERS here. This is a dictionary that contains a dotted module path to the desired match manager
   # for a given model.
   # For example:
   # MATCH_MANAGERS = {
   #    "Target": "my_custom_code.match_managers.MyCustomTargetMatchManager"
   # }
   MATCH_MANAGERS = {}

Add the path to your custom ``TargetMatchManager`` to the "Target" key of the MATCH_MANAGERS dictionary as shown in the
example.

Your can the override the default ``TargetMatchManager`` by writing your own in the location you used above.

**Remember** the ``TargetMatchManager`` must contain a ``check_for_fuzzy_match`` function and return a queryset.
See the following example for only checking for exact name matches:

.. code:: python

    class CustomTargetMatchManager(models.Manager):
    """
    Return Queryset for target with name matching string.
    """
    def check_for_fuzzy_match(self, name):
        """
        Returns a queryset exactly matching name that is received
        :param name: The string against which target names will be matched.
        :return: queryset containing matching Target(s).
        """
        queryset = super().get_queryset().filter(name=name)
        return queryset

This might be useful if a user is experiencing performance issues when ingesting targets or does not wish to allow for
a target matching to similar strings.
