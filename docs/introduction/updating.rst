Updating your TOM
=================

Keep your TOM up to date by regularly installing the most recent version of the tomtoolkit and its associated apps from
PyPI using `pip`. How exactly you do this will change based on how you handle dependencies for your project.


Upgrade from v2 to v3
---------------------

The upgrade from v2 to v3 involve several breaking changes that need to be handled by any TOM trying update to version 3.
Please follow the next steps in order to avoid complications.

1.) Update your `tomtoolkit` and `tom_app` dependencies
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This step depends on your dependency manager, but first you will need to update your TOM to depend on `tomtoolkit >=3.0.0`.
Most affiliated TOMToolkit apps will also need to be updated to their newest version.

2.) Migrate your DB
~~~~~~~~~~~~~~~~~~~

::

   ./manage.py migrate

3.) Migrate existing ReducedDatums
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This update changed how ReducedDatums are stored. We now have specific models for different types of data.
See the :ref:`Architecture Docs <ReducedDatum_label>` for a description, or 
:doc:`DataProducts API <../api/tom_dataproducts/models>` for a full code breakdown.

We want to update all of your existing data to this new scheme where possible. This could take some time for large databases.

.. Warning::
    This is a substantial DB change. Consider backing up your database before running this management command.

::

   ./manage.py migrateReducedDatums


4.) Update ``settings.py``
~~~~~~~~~~~~~~~~~~~~~~~~~~
Tomtoolkit now includes default setting stored in `tom_common.default_settings.py 
<https://github.com/TOMToolkit/tom_base/blob/dev/tom_common/default_settings.py>`_ .
This prevents users from having to update their TOMs with mandatory settings allowing for more backward compatibility
with future changes. If you wish to use these settings, please make the following changes to your ``settings.py``:

.. code-block:: python
    :caption: settings.py
    :emphasize-lines: 4, 8, 13, 20

    import logging.config
    import os
    import tempfile
    from tom_common.default_settings import *

    ...

    # Replace your existing INSTALLED_APPS with the following:
    INSTALLED_APPS = TOMTOOKIT_INSTALLED_APPS + [ 
        'custom_code',  # Include any apps you have installed for your TOM that are not in default_settings
    ]

    # Replace your existing MIDDLEWARE with the following:
    MIDDLEWARE = TOMTOOKIT_MIDDLEWARE + [
        {{ custom_middleware }}  # Include any middleware you have installed for your TOM that are not in default_settings
    ]

    ...

    # Update the CRISPY_TEMPLATE_PACK:
    CRISPY_TEMPLATE_PACK = 'bootstrap5'

    ...

.. Note::

    This will incorporate all required settings changes, and will prevent future settings updates required by TOMToolkit.
    If you would rather not rely on the `default_settings`, here is the list of required changed:

    **Installed apps:**

    - Remove `tom_alerts` and `tom_catalogs`
    - Add `tom_dataservices`
    - Replace `bootstrap4` with `django_bootstrap5`
    - Replace `crispy_bootstrap4` with `crispy_bootstrap5`

    **Other Changes:**

    - Add `CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"`


5.) Update Custom Code
~~~~~~~~~~~~~~~~~~~~~~

Your custom code will likely need updates to be compatible with the v3 changes.
Pay special attention to the following areas:

Remove references to `tom_alerts` and `tom_catalogs`
++++++++++++++++++++++++++++++++++++++++++++++++++++

These apps were deprecated and will eventually be removed from the toolkit.
Instead of these apps, use :doc:`tom_dataservices <../data_services/index>`.

Update references to `tom_dataproducts`
+++++++++++++++++++++++++++++++++++++++

Substantial updates were made to the `ReducedDatum` model infrastructure. The `ReducedDatum` model should not be used
in isolation anymore if possible. Instead, the sub models, `PhotometryReducedDatum`, `SpectroscopyReducedDatum`, and 
`AstrometryReducedDatum` should be used instead to improve communication between TOMs, and with the base TOMToolkit.

The `ReducedDatumCommon` can be extended to create new, specific data models if needed, and the existing `ReducedDatum`
model is still available for generic data, though all default references to it (such as processors) in the base toolkit
have been removed.

See the :ref:`Architecture Docs <ReducedDatum_label>` for a description of the current infrastructure, or 
:doc:`DataProducts API <../api/tom_dataproducts/models>` for a full code breakdown.

Upgrade to `bootstrap5`
+++++++++++++++++++++++

There are many invasive changes needed to upgrade to bootstrap5 from bootstrap4. These changes were necessary to stay
ahead of the curve as various projects and python distributions reach EOL.
Many of your templates may require changes.
We cannot go through a full list of the required changes here, but you can explore the following resources when attempting to implement your upgrade:

- `Bootsratp5 migration docs <https://getbootstrap.com/docs/5.0/migration/>`_
- `django-bootstrap5 migration docs <https://github.com/zostera/django-bootstrap5/blob/main/MIGRATE.md>`_
- `crispy-bootstrap5 updates <https://github.com/django-crispy-forms/crispy-bootstrap5>`_
- `TOmToolkit Bootstrap5 update PR <https://github.com/TOMToolkit/tom_base/pull/1571>`_


6.) Final Migration
~~~~~~~~~~~~~~~~~~~
New apps and custom_code changes will require a new migration. As always, take care when migrating and back up your Data base.

::

   ./manage.py migrate


Conclusion
~~~~~~~~~~
At this point, your TOM should be running on Version 3.  We know these were wide sweeping changes. If you have any
trouble with the upgrade, or find any bugs, please let us know by either making an issue on github, 
sending us a message on slack, or via email.