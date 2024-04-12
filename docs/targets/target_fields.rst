Adding Custom Fields to Targets
-------------------------------

Sometimes you’d like to store data for targets but the predefined fields
that the TOM Toolkit provides aren’t enough. The TOM Toolkit allows you
to define extra fields for your targets so you can associate different
kinds of data with them. For example, you might be studying high
redshift galaxies. In this case, it would make sense to be able to store
the redshift of your targets. You could then do a search for targets
with a redshift less than or greater than a particular value, or use the
redshift value to make decisions in your science code.

The TOM Toolkit currently supports two different methods for adding extra
fields to targets: Extending Target Models and adding Extra Fields.

Extending the Target Model
==========================
Users can extend the `Target` model by creating a custom target model in the app
where they store their custom code. This method is more flexible and allows for
more intuitive relationships between the new target fields and other code the user
may create. This method requires database migrations and a greater understanding of
Django models to implement.

By default the TOM Toolkit will use the `tom_targets.BaseTarget` model as the target model,
but users can create their own target model by subclassing `tom_targets.BaseTarget` and adding
their own fields. The TOM Toolkit will then use the custom target model if it is defined
in the `BASE_TARGET_MODEL` setting of ``settings.py``. To implement this a user will first
have to edit a ``models.py`` file in their custom code app and define a custom target model.

Subclassing `tom_targets.BaseTarget` will give the user access to all the fields and methods
of the `BaseTarget` model, but the user can also add their own fields and methods to the custom
target model. Fields from the `BaseTarget` model will be stored in a separate table from the custom
fields, and rely on separate migrations. See the
`Django documentation on multi-table inheritance. <https://docs.djangoproject.com/en/5.0/topics/db/models/#multi-table-inheritance>`__

Preparing your project for custom Target Models
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The first thing your project will need is a custom app. If you already have a custom app
(usually called ``custom_code``) you can skip this section. You can read
about custom apps in the Django tutorial
`here <https://docs.djangoproject.com/en/dev/intro/tutorial01/>`__, but
to quickly get started, the command to create a new app is as follows:

.. code:: python

   ./manage.py startapp custom_code

Where ``custom_code`` is the name of your app. You will also need to
ensure that ``custom_code`` is in your ``settings.py``. Append it to the
end of ``INSTALLED_APPS``:

.. code:: python

   ...
   INSTALLED_APPS = [
       'django.contrib.admin',
       'django.contrib.auth',
       ...
       'tom_dataproducts',
       'custom_code',
   ]
   ...

You should now have a directory within your TOM called ``custom_code``,
which looks like this:

::

   ├── custom_code
   |   ├── __init__.py
   │   ├── admin.py
   │   ├── apps.py
   │   ├── models.py
   │   ├── tests.py
   │   └── views.py
   ├── data
   ├── db.sqlite3
   ├── manage.py
   ├── mytom
   │   ├── __init__.py
   │   ├── settings.py
   │   ├── urls.py
   │   └── wsgi.py
   ├── static
   ├── templates
   └── tmp

Editing ``models.py``
~~~~~~~~~~~~~~~~~~~~~
First you will need to create a custom target model in the `models.py` file of your custom app.
The following is an example of a custom target model that adds a boolean field and a number field:

.. code:: python

    from django.db import models

    from tom_targets.base_models import BaseTarget


    class UserDefinedTarget(BaseTarget):
        example_bool = models.BooleanField(default=False)
        example_number = models.FloatField(default=0)

        # Set Hidden Fields
        example_bool.hidden = True

        class Meta:
            verbose_name = "target"
            permissions = (
                ('view_target', 'View Target'),
                ('add_target', 'Add Target'),
                ('change_target', 'Change Target'),
                ('delete_target', 'Delete Target'),
            )

The model name, `UserDefinedTarget` in the example, can be replaced by whatever CamelCase name you want, but
it must be a subclass of `tom_targets.BaseTarget`. The permissions in the class Meta are required for the
TOM Toolkit to work properly. The `hidden` attribute can be set to `True` to hide the field from the target
detail page.

Editing ``settings.py``
~~~~~~~~~~~~~~~~~~~~~~~
Next you will need to tell the TOM Toolkit to use your custom target model. In the `settings.py` file of your
project, you will need to add the following line:

.. code:: python

    BASE_TARGET_MODEL = 'custom_code.models.UserDefinedTarget'

Changing `custom_code` to the name of your custom app and `UserDefinedTarget` to the name of your custom target model.

Creating Migrations
~~~~~~~~~~~~~~~~~~~~
After you have created your custom target model, you will need to create a migration for it. To do this, run the
following command:

.. code:: python

    ./manage.py makemigrations

This will create a migration file in the `migrations` directory of your custom app. You can then apply the migration
by running:

.. code:: python

    ./manage.py migrate

This will build the appropriate tables in your database for your custom target model.

Adding ``Extra Fields``
=======================
If a user does not want to create a custom target model, they can use the `EXTRA_FIELDS`
setting to add extra fields to the `Target` model. This method is simpler and does not require
any database migrations, but is less flexible than creating a custom target model.

**Note**: There is a performance hit when using extra fields. Try to use
the built in fields whenever possible.

Enabling extra fields
~~~~~~~~~~~~~~~~~~~~~

To start, find the `EXTRA_FIELDS` definition in your ``settings.py``:

.. code:: python

   # Define extra target fields here. Types can be any of "number", "string", "boolean" or "datetime"
   # For example:
   # EXTRA_FIELDS = [
   #     {'name': 'redshift', 'type': 'number'},
   #     {'name': 'discoverer', 'type': 'string'}
   #     {'name': 'eligible', 'type': 'boolean'},
   #     {'name': 'dicovery_date', 'type': 'datetime'}
   # ]
   EXTRA_FIELDS = []

We can define any number of extra fields in the array. Each item in the
array is a dictionary with two values: name and type. Name is simply
what you would like to name your field. Type is the datatype of the
field and can be one of: ``number``, ``string``, ``boolean`` or
``datetime``. These types allow the TOM Toolkit to properly store,
filter and display these values elsewhere.

As an example, let’s change the setting to look like this:

.. code:: python

    EXTRA_FIELDS = [
        {'name': 'redshift', 'type': 'number'},
    ]

This will make an extra field with the name “redshift” and a type of
“number” available to add to our targets.

Using extra fields
~~~~~~~~~~~~~~~~~~

Now if you go to the target creation page, you should see the new field
available:

|image0|

And if we go to our list of targets, we should see redshift as a field
available to filter on:

|image1|

Extra fields with the ``number`` type allow filtering on range of
values. The same goes for fields with the ``datetime`` type. ``string``
types to a case insensitive inclusive search, and ``boolean`` fields to
a simple matching comparison.

Of course, redshift does appear on our target’s display page as well:

|image2|

To hide extra fields from the target page, we can set the “hidden” key
(this doesn’t affect filtering and searching):

.. code:: python

    EXTRA_FIELDS = [
        {'name': 'redshift', 'type': 'number', 'hidden': True},
    ]

And we can set a default value for an extra field by including a default
key/value pair:

.. code:: python

    EXTRA_FIELDS = [
        {'name': 'redshift', 'type': 'number', 'default': 0},
    ]

Displaying extra fields in templates
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If we want to display the redshift in other places, we can use a
template filter to do that. For example, we might want to display the
redshift value in the target list table.

At the top of our template make sure to load ``targets_extras``:

::

   {% raw %}
    {% load targets_extras %}
   {% endraw %}

Now we can use the ``target_extra_field`` filter wherever a target
object is available in the template context:

::

   {% raw %}
    {{ target|target_extra_field:"redshift" }}
   {% endraw %}

The result is the redshift value being printed on the template:

|image3|

Working with extra fields programatically
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you’d like to update or save extra fields to your targets in code,
there are a few methods you can use. The simplest is to simply pass in a
dictionary of extra data to your target’s ``save()`` method using the
``extras`` keyword argument:

.. code:: python

   target = Target.objects.get(name='example')
   target.save(extras={'foo': 42})

The example target above will now have an extra field “foo” with the
value 42.

For more precise control, you can access ``TargetExtra`` models
directly. To remove an extra, for example:

.. code:: python

   target = Target.objects.get(name='example')
   target_extra = target.targetextra_set.get(key='foo')
   target_extra.delete()

The above deleted the target extra on a target with the key of “foo”.

.. |image0| image:: /_static/target_fields_doc/redshift.png
.. |image1| image:: /_static/target_fields_doc/redshift_filter.png
.. |image2| image:: /_static/target_fields_doc/redshift_display.png
.. |image3| image:: /_static/target_fields_doc/redshift_tag.png
