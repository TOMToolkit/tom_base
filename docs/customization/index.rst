Customization
=============

The TOM Toolkit is deliberately designed as an adaptable framework to enable users to customize
all aspects of it.  This includes both "look and feel" aspects of the appearance of the user interface,
to adding new functionality and automating aspects of your workflow.

The :doc:`Programming Resources </introduction/programming_resources>` page provides some quick links to a number of useful reference sources
relating to software used in the TOM Toolkit: HTML, CSS, Python, and Django

User Interface Appearance and Layout
------------------------------------

The TOM's user interface is built on top of `Django's template engine <https://docs.djangoproject.com/en/6.0/ref/templates/>`_.
This template system allows us to design pages which can be populated with variables and even functions called ``templatetags``,
to adapt the content and provide functionality - without duplication of content.

The Toolkit provides a number of built-in templates which you can see in the out-of-the-box TOM system.
Any or all of these templates can be overridden if you want to change the color palette or even the entire layout.
:doc:`Customizing TOM Templates <customize_templates>` describes how to do this.

We provide a library of widgets to perform common functions, such as buttons.
:doc:`TOM Widgets <widgets>` describes how to make use of these in your page.

Adding Pages and Functionality
------------------------------

You can also add entirely new pages to the TOM user interface, to display either static content or display and interact
with data in the database.  The process for doing this is described in
:doc:`Adding new Pages to your TOM <adding_pages>`.

Alternatively, you may not need to add a whole new page, but would like to "embed" a function to display data in
a customized way within an existing page.  In that case, you probably want to develop a new `templatetag
<https://docs.djangoproject.com/en/6.0/howto/custom-template-tags/#:~:text=templatetags%20directory%2C%20at%20the%20same%20level%20as>`_.
:doc:`This page <customize_template_tags>` describes how to do this.


Data Visualization Tools
------------------------

The data visualization tools in the Toolkit include a number of interactive plots and skymaps.  You can add
your own custom plots following the guidelines in :doc:`Creating Plots from TOM Data </managing_data/plotting_data>`.

We are increasingly using `HTMX <https://htmx.org/>`_ within the Toolkit to provide more responsive interactive elements
such as search functions, while minimizing the Toolkit's dependency on Javascript.  This choice helps us minimize the
user learning curve (though you're welcome to use Javascript if you like!).  One area where HTMX has proven useful is in
in the interactive table search functions.  :doc:`Click here </customization/htmx_tables>` to learn how to build interactive tables with
filtering, sorting, and pagination using django-tables2 and HTMX.

Custom Code Hooks
-----------------

Code hooks provide a mechanism for triggering a pre-defined action whenever a certain condition happens.
One example of this is the TOM's data processors which are triggered whenever a data product is uploaded, but you
can easily imagine many other use cases within your workflow.

:doc:`Running Custom Code Hooks </code/custom_code>` demonstrates how to implement you own custom code hook.

Encrypting Sensitive Data
-------------------------

Some data held in a TOM can be sensitive, such as user passwords.  For security's sake, it is best that these fields
are encrypted, and the TOM provides support for this.  :doc:`Click here </customization/encrypted_model_fields>` to learn how to
make use of encrypted fields your TOMToolkit app.

Testing
-------

If you implement new features, it is a very good idea to include unit tests to verify that the functionality works,
both right now and after future upgrades.  To test your TOM's functionality, see :doc:`Testing TOMs </customization/testing_toms>`.

Asynchronous Tasks
------------------

If a function is expected to take more than a few minutes - for example a data reduction pipeline - it is advisable
to consider implementing it as an asynchronous task.  This will avoid the browser timing out while the task is executing.

More information on implementing asynchronous tasks within a TOM can be found in :doc:`Background Tasks </code/backgroundtasks>`.
