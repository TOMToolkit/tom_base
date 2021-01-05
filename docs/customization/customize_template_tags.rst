Customizing Template Tags
=========================

The TOM Toolkit is designed to be as customizable as possible. A number
of UI objects are rendered as Django templatetags. Django has quite a
few `built-in template
tags <https://docs.djangoproject.com/en/3.0/ref/templates/builtins/>`__,
but also allows the creation of `custom template
tags <https://docs.djangoproject.com/en/3.0/howto/custom-template-tags/>`__,
which the TOM Toolkit leverages heavily.

However, it’s possible that a TOM Toolkit template tag doesn’t quite
meet your needs. Maybe the axis labels for photometry plotting aren’t
quite what you’re looking for, or the target data isn’t formatted the
way you’d like. This tutorial will show you how to write your own
template tag to suit your own program better.

Preparing your project for custom template tags
-----------------------------------------------

The first thing your project will need is a custom app. You can read
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

Next, you’ll need to add a ``templatetags`` directory within
``custom_code``. Create an empty file called ``__init__.py`` within that
directory. Finally, we need a file to put the code for our custom
template tags. Add a file in ``custom_code`` called ``custom_extras``.
It’s convention to use ``_extras`` within your template tag module name.

Your ``custom_code`` directory should look like this:

::

   └── custom_code
       ├── __init__.py
       ├── admin.py
       ├── apps.py
       ├── models.py
       ├── templatetags
       |   ├── __init__.py
       |   └── custom_extras.py
       ├── tests.py
       └── views.py

Writing a custom template tag
-----------------------------

For our template tag, we’re going to write a tag that displays the
timestamp and magnitude for the most recent photometry point available
for a target. There are three aspects to a template tag:

-  The code in ``custom_extras`` to run the logic to get the data we’ll
   be displaying
-  The partial template to render the data
-  Putting the custom tag somewhere we’d like it displayed

The Python code
~~~~~~~~~~~~~~~

We’re going to write a ``recent_photometry`` function in our
``custom_extras`` first. Step one is the necessary import and
initialization of the template library:

.. code:: python

   from django import template


   register = template.Library()

Now, to the ``recent_photometry`` function. A couple notes about the
approach here:

-  The function will have the decorator ``@register.inclusion_tag()``.
   There are a couple of different types of template tags, but we’re
   using the ``inclusion_tag`` because it renders a template, allowing
   us to customize how it looks. The ``simple_tag`` is a different type
   of template tag that simply modifies data, so that won’t work for us.
-  Within the decorator is a path to the partial template that will
   render the data–this doesn’t exist yet, but remember the file name
   we’re using!
-  We’d like to get the latest photometry values for a specific target,
   so we’ll need to pass a ``Target`` as a parameter.
-  We’d also like to be able to specify how many photometry points we
   care about, so let’s also include a keyword argument that defaults to
   just 1.

.. code:: python

   from django import template


   register = template.Library()


   @register.inclusion_tag('custom_code/partials/recent_photometry.html')
   def recent_photometry(target, num_points=1):
       return {}

You can see that we’ll eventually be returning a dictionary, but first
we need to add our logic. We’ll need to use the ``Target`` passed in to
get all ``ReducedDatum`` objects for that ``Target`` with a
``data_type`` of ``photometry``. Then we’ll need to order by
``timestamp`` descending, and slice just the first few. Make sure to
take note of the imports in this step!

.. code:: python

   import json

   from django import template

   from tom_dataproducts.models import ReducedDatum


   register = template.Library()


   @register.inclusion_tag('custom_code/partials/recent_photometry.html')
   def recent_photometry(target, num_points=1):
       photometry = ReducedDatum.objects.filter(data_type='photometry').order_by('-timestamp')[:num_points]
       return {'recent_photometry': [(datum.timestamp, json.loads(datum.value)['magnitude']) for datum in photometry]}

It’s only a couple of lines, but there’s a lot going on here. The first
line does the aforemention database query and slices the first point of
the ``QuerySet``. The second line constructs a dictionary–the only key
is ``recent_photometry``, and the corresponding value is a list of
tuples. Each tuple has the timestamp as the first item, and the
magnitude as the second item.

Ultimately, this template tag will, when included, return the most
recent photometry points for a ``Target``. But it can’t display
anything!

The partial template
~~~~~~~~~~~~~~~~~~~~

So now we need to create
``custom_code/templates/custom_code/partials/recent_photometry.html``.
We’ll need to add yet another series of directories and files. Your
directory structure should now look like this:

Let’s start with the partial template. We’ll need to add yet another
series of directories and files. Add the following to your directory
structure:

::

   └── custom_code
       └── templates
           └── custom_code
               └── partials
                   └── recent_photometry.html

Your complete directory structure should look like this:

::

   └── custom_code
       ├── __init__.py
       ├── admin.py
       ├── apps.py
       ├── models.py
       ├── templates
       |   └── custom_code
       |       └── partials
       |           └── recent_photometry.html
       ├── templatetags
       |   ├── __init__.py
       |   └── custom_extras.py
       ├── tests.py
       └── views.py

And let’s open up ``recent_photometry.html`` and get to work.

.. code:: html

   <div class="card">
       <div class="card-header">
         Recent Photometry
       </div>
       <table class="table">
           <thead><tr><th>Timestamp</th><th>Magnitude</th></tr></thead>
           <tbody>
           {% for datum in recent_photometry %}
           <tr>
               <td>{{ datum.0 }}</td>
               <td>{{ datum.1 }}</td>
           </tr>
           {% empty %}
           <tr>
               <td colspan="2">No recent photometry.</td>
           </tr>
           {% endfor %}
           </tbody>
       </table>
   </div>

This template looks suspiciously like a few others in the TOM Toolkit,
but that’s okay! It will just render a two-column table with columns for
timestamp and magnitude. The dictionary we returned is accessible to the
template, which is why this line works:

.. code:: html

   {% for datum in recent_photometry %}

It iterates over the value referred to by ``recent_photometry``, which,
if you recall, is a list of tuples. Then it renders each element of the
tuple in a ``<td>`` element.

So we have a partial template and a template tag that can be used
anywhere, but we have to put it somewhere!

Using the template tag
~~~~~~~~~~~~~~~~~~~~~~

The target detail page seems like a logical place for this, so let’s go
there. First, we need to override our ``target_detail.html`` template.
If you haven’t read the tutorial on template overriding, you can do so
`here <customize_templates>`__– in the meantime, you’ll need to add
``target_detail.html`` to ``templates/tom_targets/`` in the top level of
your project. Your project directory should look like this:

::

   ├── custom_code
   ├── data
   ├── db.sqlite3
   ├── manage.py
   ├── mytom
   ├── static
   ├── templates
   │   └── tom_targets
   │       └── target_detail.html
   └── tmp

Then, you’ll need to copy the contents of ``target_detail.html`` in the
base TOM Toolkit to your ``target_detail.html``. You can find that file
on
`Github <https://github.com/TOMToolkit/tom_base/blob/main/tom_targets/templates/tom_targets/target_detail.html>`__.

Near the top of the file, there’s a series of template tags that are
loaded in. Add ``custom_extras`` to that list:

.. code:: html

   {% extends 'tom_common/base.html' %}
   {% load comments bootstrap4 tom_common_extras targets_extras observation_extras dataproduct_extras publication_extras custom_extras static cache %}
   ...

Then, put your templatetag in the HTML somewhere, passing in ``object``
(which refers to the object value of the current template context) and
the desired number of photometry points:

.. code:: html

   ...
   {% endif %}
   {% target_buttons object %}
   {% target_data object %}
   {% if object.type == 'SIDEREAL' %}
   {% aladin object %}
   {% endif %}
   {% recent_photometry object num_points=3 %}
   ...

The new table should be displayed on your target detail page! Not only
that, but you’ll now be able to include that template tag on other
pages, too. And if it doesn’t quite meet your needs–perhaps you want the
most recent photometry points for all targets, for example–it can be
easily modified.

As far as this template tag goes, as of this tutorial, it’s now a part
of the base TOM Toolkit, but all of the information here should provide
you with the ability to write your own.
