Welcome to the TOM Toolkit's documentation!
===========================================

.. link-button:: introduction/getting_started.html
    :text: Quickstart Guide
    :classes: btn-info

.. toctree::
  :maxdepth: 3
  :hidden:

  introduction/credits
  introduction/index
  introduction/about
  introduction/support
  introduction/troubleshooting

Introduction
------------

The TOM (Target and Observation Manager) Toolkit project was started in early 2018 with the goal of simplifying the development of next generation software for the rapidly evolving field of astronomy. Read more :doc:`about TOMs<introduction/about>` and the motivation for them.

:doc:`TOM  Toolkit Architecture <introduction/tomarchitecture>` - This document describes the architecture of the TOM Toolkit at a
high level. Read this first if you're interested in how the TOM Toolkit works.

:doc:`Getting Started with the TOM Toolkit<introduction/getting_started>` - First steps for getting a TOM up and running.

:doc:`TOM Workflow <introduction/workflow>` - The general workflow used with TOMs.

:doc:`Programming Resources <introduction/resources>` - Resources for learning the core components of the TOM Toolkit:
HTML, CSS, Python, and Django

:doc:`Frequently Asked Questions <introduction/faqs>` - Look here for a potential quick answer to a common question.

:doc:`Troubleshooting <introduction/troubleshooting>` - Find solutions to common problems or information on how to debug an issue.

Interested in seeing what a TOM can do? Take a look at our `demonstration TOM <https://tom-demo.lco.global>`_, where we show off the features of the TOM Toolkit.

If you'd like to know what we're working on, check out the `TOM Toolkit project board <https://github.com/TOMToolkit/tom_base/projects/1>`_.


Topics
------

.. toctree::
  :maxdepth: 2
  :hidden:

  targets/index
  brokers/index
  observing/index
  managing_data/index
  customization/index
  common/permissions
  common/latex_generation
  code/index
  deployment/index
  common/customsettings


:doc:`Targets <targets/index>` - Learn all about how to manage Targets in a TOM.

:doc:`Brokers <brokers/index>` - Find out about querying brokers in the TOM, which are available, and writing your own.

:doc:`Observing <observing/index>` - Tutorials on submitting observations, customizing submission, and the available facilities.

:doc:`Managing Data <managing_data/index>` - Customize plots, upload data, and even integrate a data reduction pipeline.

:doc:`Customization <customization/index>` - Customize and create new views in your TOM.

:doc:`The Permissions System <common/permissions>` - Use the permissions system to limit access to targets in your TOM.

:doc:`LaTeX Generation <common/latex_generation>` - Generate data tables for your targets and observations

:doc:`Interacting with your TOM through code <code/index>` - Learn how to programmatically interact with your TOM.

:doc:`Deploying your TOM Online <deployment/index>` - Resources for deploying your TOM to a cloud provider

:doc:`TOM Settings <common/customsettings>` - Reference and description for the available settings values to be added to/edited in your project's ``settings.py``.

Contributing
------------

If you find an issue, you need help with your TOM, you have a useful idea, or you wrote a module you'd like to be
included in the TOM Toolkit, start with the :doc:`Contribution Guide <introduction/contributing>`.

Acknowledging the TOM Toolkit
-----------------------------

We hope you find our software useful for your research.  If so, we would be grateful
if you can include a brief acknowledgement in your papers and presentations, for example
"This research made use of `The TOM Toolkit <https://tom-toolkit.readthedocs.io/>`_".
We would also very much appreciate you including a citation to our paper describing
the Toolkit `Street, R.A. et al., 2018, SPIE, 10707, 11 <http://adsabs.harvard.edu/abs/2018SPIE10707E..11S>`_
(to export the BibTeX please click `here <https://ui.adsabs.harvard.edu/abs/2018SPIE10707E..11S/exportcitation>`_).

.. toctree::
  :maxdepth: 1

  introduction/acknowledging_tom_toolkit

Support
-------

Looking for help? Want to request a feature? Have questions about Github Issues? Take a look at the :doc:`support guide
<introduction/support>`.

If you just need an idea, checkout out the :doc:`examples<examples>` of existing TOMs built with the TOM Toolkit.

.. toctree::
  :maxdepth: 1
  :hidden:

  examples
  introduction/contributing
  Releases <https://github.com/TOMToolkit/tom_base/releases>
  Release Notes <https://github.com/TOMToolkit/tom_base/blob/main/releasenotes.md>
  Github <https://github.com/TOMToolkit>

API Documentation
-----------------

.. toctree::
  :maxdepth: 2

  api/modules
  api/plugins
  api/affiliated

******************
Indices and tables
******************

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

About the TOM Toolkit
---------------------

The TOM Toolkit is managed by Las Cumbres Observatory, with generous
financial support from the `National Science Foundation <https://www.nsf.gov/>`_ grant 2209852.
We are also grateful for support from the `Heising-Simons Foundation
<https://hsfoundation.org>`_ and the `Zegar Family Foundation
<https://sites.google.com/zegarff.org/site>`_ at the start of the project.


Read about the project and the motivations behind it on the :doc:`About page <introduction/about>`.
