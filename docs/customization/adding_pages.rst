Adding pages to your TOM
------------------------

The TOM Toolkit provides many views (pages) by default, but at some
point you may want to add pages of your own. These could be simple
static pages like project or grant information. Or they can be fully
dynamic, displaying data from the database and containing forms of their
own.

In this tutorial we’ll start out by adding a simple “About” page to our
TOM. Then to spice it up a little we’ll add some dynamic info to the
page (a list of targets). Finally we’ll learn how Django can help us
create even more interactive pages.

A simple template page
~~~~~~~~~~~~~~~~~~~~~~

Let’s get started with some code and we’ll explain it piece by piece
afterwards.

First, let’s create a new file ``about.html`` and place it in the
``templates/`` directory at the root of our TOM. This file will contain
the content of our new page.

.. code:: html

   <p>
   To know that we know what we know, and to know that we do not know
   what we do not know, that is true knowledge. <br/>
   <strong>Nicolaus Copernicus</strong>
   </p>

Next we need to tell Django about this new page and what url to serve it
from. Open the ``urls.py`` file (next to ``settings.py``) and modify it
so that it looks something like this (you may have additional urls
already, the important part is the one relevant to ``about.html``):

.. code:: python

   from django.urls import path, include
   from django.views.generic import TemplateView

   urlpatterns = [
       path('', include('tom_common.urls')),
       path('about/', TemplateView.as_view(template_name='about.html'), name='about')
   ]

Notice the ``path`` function we use here. It takes three arguments.
Argument one is the path in which this page should be made available in
our TOM. In this case, we used the sensible path “about/”. The second
argument is the view function. In this case we passed in a
`TemplateView <https://docs.djangoproject.com/en/2.2/ref/class-based-views/base/#templateview>`__
. We’ll talk about view functions a bit later, but just know that this
class simply takes the template it should render and renders it. The
last argument is the name of the url. This is so we can refer to this
path elsewhere in the application without the need to hardcode urls.

Enough techno blabber. Launch your TOM and navigate to
`/about/ <http://127.0.0.1:8000/about/>`__. You should see something
like this:

|image0|

That’s progress, but our new page is pretty ugly. The navigation bar is
missing and we don’t have any of the nice CSS that makes the rest of the
TOM pages look good! But wait, before you start copying in lines of
HTML, know that all we need to do is extend
`tom_common/base.html <https://github.com/TOMToolkit/tom_base/blob/main/tom_common/templates/tom_common/base.html>`__
to get all that back. You can read more about extending templates from
the guide on `Customizing TOM
Templates </customization/customize_templates>`__. Let’s modify
``about.html`` to extend the base template:

.. code:: html

   {% extends 'tom_common/base.html' %}
   {% block content %}
   <p>
   To know that we know what we know, and to know that we do not know
   what we do not know, that is true knowledge. <br/>
   <strong>Nicolaus Copernicus</strong>
   </p>
   {% endblock %}

Now when you reload the page you should see this:

|image1|

Much better! By extending a template and providing a ``content`` block,
we are able to make consistent looking pages without copying and pasting
any code.

You can read more about template inheritance in `Django’s official
docs <https://docs.djangoproject.com/en/2.2/ref/templates/language/#template-inheritance>`__

Adding in dynamic data
~~~~~~~~~~~~~~~~~~~~~~

We now know how to add basic static pages. But what if we want to show
data from our database? Let’s try adding a list of all the targets in
our TOM to the about page. This is slightly more complex, so we’re going
to create a new file, ``views.py`` alongside our ``urls.py`` file. Add
the following content:

.. code:: python

   from django.views.generic import TemplateView
   from tom_observations.models import Target


   class AboutView(TemplateView):
       template_name = 'about.html'

       def get_context_data(self, **kwargs):
           return {'targets': Target.objects.all()}

Notice we are still using the ``TemplateView`` here. The only addition
is that we are implementing ``get_context_data`` which returns a
dictionary of data that should be available to our template. In this
case, we are returning all the targets in our TOM.

Let’s modify our ``urls.py`` to use our new view:

.. code:: python

   from django.urls import path, include
   from .views import AboutView

   urlpatterns = [
       path('', include('tom_common.urls')),
       path('about/', AboutView.as_view(), name='about')
   ]

We’ve replaced the import of ``TemplateView`` with an import of the view
class we just wrote, and modified the call to ``path()`` accordingly.

Lastly let’s update our ``about.html`` template to actually show the
list of targets:

.. code:: html

   {% extends 'tom_common/base.html' %}
   {% block content %}
   <p>
   To know that we know what we know, and to know that we do not know
   what we do not know, that is true knowledge. <br/>
   <strong>Nicolaus Copernicus</strong>
   </p>
   <ul>
     {% for target in targets %}
     <li>{{ target.name }}</li>
     {% endfor %}
   </ul>
   {% endblock %}

``targets`` in this template refers to the key in the dictionary we
returned in the ``get_context_data`` method in our view. We can add
anything to the context dictionary and have access to it in our
templates. In this particular example, we’re iterating over all of the
targets in our TOM and displaying all of their names. If you don’t see
anything, make sure you have targets in your TOM!

Reloading your about page, you should now see something like this:

|image2|

If the page looks exactly the same as last time, you might need to add
some targets. Navigate to
`http://localhost:8000/targets/ <http://cygnus.lco.gtn:8000/targets/>`__
to do so. ### Class based views Django has the concept of `class based
views <https://docs.djangoproject.com/en/2.2/topics/class-based-views/intro/>`__.
These classes do one job: they take in an HTTP request and return a
response. In this tutorial we took advantage of Django’s
`TemplateView <https://docs.djangoproject.com/en/2.2/ref/class-based-views/base/#templateview>`__
which does a simple job of rendering templates. Django has `many more
built in class based
views <https://docs.djangoproject.com/en/2.2/topics/class-based-views/generic-display/>`__
that can be taken advantage of. For example, instead of using the
``TemplateView`` for rendering a list of Targets, we could have used the
`ListView <https://docs.djangoproject.com/en/2.2/topics/class-based-views/generic-display/#generic-views-of-objects>`__
which provides additional functionality, such as pagination and
filtering.

When working with class based views, you’ll almost always subclass them.
We did this with our ``AboutView`` earlier, and changed the
``TemplateView``\ ’s behavior to include a list of our targets. Herein
lies the power of class based views. You can even subclass the views
that ship with the TOM Toolkit itself. So for example, if you don’t like
how the
`TargetListView <https://github.com/TOMToolkit/tom_base/blob/15870172e842bcbac17bd4a4b71c9e016b270cf9/tom_targets/views.py#L29>`__
in the base TOM Toolkit behaves, you could subclass it in your TOM:

.. code:: python

   from tom_targets.views import TargetListView

   class MyCustomTargetListView(TargetListView):
       template_name = 'mysupertargetlist.html'
       paginate_by = 100

Wrapping it all up
~~~~~~~~~~~~~~~~~~

In this tutorial we learned how to not only add static pages to our TOM,
but also how to display some information from our database. Along the
way we learned about Django’s `class based
views <https://docs.djangoproject.com/en/2.2/topics/class-based-views/intro/>`__
as well as some of the things we could use them for.

We didn’t get into how to display forms or receive other parameters in
our views, but some `light reading the Django
docs <https://docs.djangoproject.com/en/2.2/intro/tutorial04/#write-a-simple-form>`__
could familiarize one with those concepts.

.. |image0| image:: /_static/adding_pages_doc/quote.png
.. |image1| image:: /_static/adding_pages_doc/base.png
.. |image2| image:: /_static/adding_pages_doc/targets.png
