FAQ
###

Can I use Jupyter Notebooks with my TOM?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Yes. First install jupyterlab into your TOM virtualenv:

::

   pip install jupyterlab

Inside your TOM directory, use the following management command to
launch the notebook server:

::

   ./manage.py shell_plus --notebook

Under the new notebook menu, choose “Django Shell-Plus”. This will
create a new notebook in the correct TOM context.

There is also a `tutorial <../common/scripts>`__ on interacting with
your TOM using Jupyter notebooks.

What are tags on the Target form?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can add tags to targets via the target create/update forms or
programmatically. These are meant to be arbitrary data associated with a
target. You can then search for targets via tags on the target list
page, by entering the “key” and/or “value” fields in the filter list.
They will also be displayed on the target detail pages.

If you’d like to have more control over extra target data, see the
documentation on `Adding Custom Target
Fields <../targets/target_fields>`__.

I try to observe a target with LCO but get an error.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You might not have added your LCO api key to your settings file under
the ``FACILITIES`` settings. See `Custom
Settings <../uncategorized/customsettings#facilities>`__ for more
details.

How do I create a super user (PI)?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can create a new superuser using the built in management command:

::

   ./manage.py createsuperuser

The ``manage.py`` file can be found in the root of your project.

Alternatively, you can give a user superuser status if you are already
logged in as a superuser by visiting the admin page for users:
http://127.0.0.1/admin/auth/user/

My science requires more parameters than are provided by the TOM Toolkit.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

It is possible to add additional parameters to your targets within the
TOM. See the documentation on `Adding Custom Target
Fields <../targets/target_fields>`__.

Yuck! My TOM is ugly. How do I change how it looks?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You have a few options. If you’d like to rearrange the layout or
information on the page, you can follow the tutorial on `Customizing
your TOM <../customization/customize_templates>`__. If you’d like to
modify colors, typography, etc you’ll want to use CSS.
`W3Schools <https://www.w3schools.com/Css/>`__ is a good resource if you
are unfamiliar with Cascading Style Sheets.

How do I add a new page to my TOM?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

We would recommend you read the `Django
tutorial <https://docs.djangoproject.com/en/2.2/contents/>`__ 🙂. But if
you want the quick and dirty, edit the ``urls.py`` (located next to
``settings.py``):

.. code:: python

   from django.urls import path, include
   from django.views.generic import TemplateView

   urlpatterns = [
       path('', include('tom_common.urls')),
       path('newpage/', TemplateView.as_view(template_name='newpage.html'), name='newpage')
   ]

And make sure ``newpage.html`` is located within the ``templates/``
directory in your project.

This will make the contents of ``newpage.html`` available under the path
`/newpage/ <http://127.0.0.1/newpage/>`__.

Who is AnonymousUser?
~~~~~~~~~~~~~~~~~~~~~

AnonymousUser is a special profile that django-guardian, our permissions
library, creates automatically. AnonymousUser represents an
unauthenticated user. The user has no first name, last name, or
password, and allows unauthenticated users to view unprotected pages
within your TOM. You can choose to delete the user if you don’t want any
pages to be visible without logging in.

How can I display an error message when authentication to an external facility fails?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For any modules exposing external services, such as brokers, harvesters,
or facilities, a failed authentication should raise an
``ImproperCredentialsException``. Exceptions of this type are caught by
the TOM Toolkit’s built-in ``ExternalServiceMiddleware``. This
middleware will display an error at the top of the page and redirect the
user to the home page.
