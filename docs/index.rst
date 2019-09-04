Welcome to TOM Toolkit's documentation!
=======================================

.. toctree::
  :maxdepth: 1
  :hidden:

  introduction/index
  customization/index
  advanced/index
  deployment/index

Introduction
------------

Start with the :doc:`introduction<introduction/index>` if you are new to using the TOM Toolkit.

:doc:`Architecture <introduction/tomarchitecture>` - This document describes the architecture of the TOM Toolkit at a
high level. Read this first if you're interested in how the TOM Toolkit works.

:doc:`Getting Started <introduction/getting_started>` - First steps for getting a TOM up and running.

:doc:`Workflow <introduction/workflow>` - The general workflow used with TOMs.

Extending and Customizing
-------------------------

Start here to learn how to customize the look and feel of your TOM or add new functionality.

:doc:`Custom Settings <customization/customsettings>` - Settings available to the TOM Toolkit which you may want to
configure.

:doc:`Customizing TOM Templates <customization/customize_templates>` - Learn how to override built in TOM templates to
change the look and feel of your TOM.

:doc:`Adding new Pages to your TOM <customization/adding_pages>` - Learn how to add entirely new pages to your TOM,
displaying static html pages or dynamic database-driven content.

:doc:`Adding Custom Target Fields <customization/target_fields>` - Learn how to add custom fields to your TOM Targets if the
defaults do not suffice.

:doc:`Adding Custom Data Processing <customization/customizing_data_processing>` - Learn how you can process data into your
TOM from uploaded data products.

:doc:`Building a TOM Alert Broker <customization/create_broker>` - Learn how to build an Alert Broker module to add new
sources of targets to your TOM.

:doc:`Changing Request Submission Behavior <customization/customize_observations>` - Learn how to customize the LCO
Observation Module in order to add additional parameters to observation requests sent to the LCO Network.

:doc:`Creating Plots from TOM Data <customization/plotting_data>` - Learn how to create plots using plot.ly and your TOM
data to display anywhere in your TOM.

:doc:`The Permissions System <customization/permissions>` - Use the permissions system to limit access to targets in your
TOM.

:doc:`Automating Tasks <customization/automation>` - Run commands automatically to keep your TOM working even when you
aren’t

Advanced Topics
---------------

:doc:`Background Tasks <advanced/backgroundtasks>` - Learn how to set up an asynchronous task library to handle long
running and/or concurrent functions.

:doc:`Building a TOM Observation Facility Module <advanced/observation_module>` - Learn to build a module which will
allow your TOM to submit observation requests to observatories.

:doc:`Running Custom Code Hooks <advanced/custom_code>` - Learn how to run your own scripts when certain actions happen
within your TOM (for example, an observation completes).

:doc:`Scripting your TOM with Jupyter Notebooks <advanced/scripts>` - Use a Jupyter notebook (or just a python
console/scripts) to interact directly with your TOM.

Deployment
----------

Once you’ve got a TOM up and running on your machine, you’ll probably want to deploy it somewhere so it is permanently
accessible by you and your colleagues.

:doc:`General Deployment Tips <deployment/deployment_tips>` - Read this first before deploying your TOM for others to use.

:doc:`Deploy to Heroku <deployment/deployment_heroku>` - Heroku is a PaaS that allows you to publicly deploy your web applications without the need for managing the infrastructure yourself.

:doc:`Using Amazon S3 to Store Data for a TOM <deployment/amazons3>` - Enable storing data on the cloud storage service Amazon S3 instead of your local disk.

Contributing
------------

If you find an issue, you need help with your TOM, you have a useful idea, or you wrote a module you'd like to be
included in the TOM Toolkit, start with the `Contribution Guide <https://tomtoolkit.github.io/docs/contributing>`_.

Support
-------

Looking for help? Want to request a feature? Have questions about Github Issues? Take a look at the :doc:`support guide
<support>`.

About the TOM Toolkit
---------------------

Read about the project and the motivations behind in on the `About page <https://tomtoolkit.github.io/about>`_.

API Documentation
-----------------

.. toctree::
  :maxdepth: 2

  modules

.. toctree::
  :maxdepth: 1
  :hidden:

  Contributing <https://tomtoolkit.github.io/docs/contributing>
  support
  About <https://tomtoolkit.github.io/about>

******************
Indices and tables
******************

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`