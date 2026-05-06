TOM Toolkit
===========

.. toctree::
  :maxdepth: 2
  :hidden:

  Getting started <introduction/getting_started>
  Configuration <common/customsettings>
  Targets <targets/index>
  Dataservices <brokers/index>
  Observing <observing/index>
  Data <managing_data/index>
  Customization <customization/index>
  APIs <code/index>
  Deploy <deployment/index>
  Plugins <code/plugins>

Introduction
------------

Target and Observation Manager systems (TOMs, aka marshals) are designed to help researchers
to manage all aspects of astronomical programs.  With data rates and volumes increasing, keeping track of
all targets, data products and observations can be a challenge.  A TOM system provides a flexible database
of all project information, with a built-in observation and data analysis control system,
together with communication and data visualization tools.
Hundreds of users can then use them to collaborate scientifically, share results and to coordinate
the acquisition of new data.

The TOM (Target and Observation Manager) Toolkit is designed to make it easy for astronomers to build
and customize a TOM system for their science goals.  The package includes a full-featured TOM system
out of the box, and this documentation describes how you can extend this system for your own needs.

More information about the project can be found in :doc:`here<introduction/about>`.

Installation & Configuration
----------------------------

Full instructions for installing the package and creating your own TOM system can be found in :doc:`getting started<introduction/getting_started>`.

A range of common configuration options are covered in :doc:`custom settings<common/customsettings>`, including options
to control user permissions.

Examples
--------

It's always helpful to have template projects as a reference, so we run a `TOM demo system <https://tom-demo.lco.global/>`__
where you can explore the TOM's features.  If you want to see how this was done, you can explore the code on
`Github <https://github.com/LCOGT/tom-demo>`__.

Customizing your system
-----------------------

The TOM is designed to be flexible, and there are a number of ways to customize it, from the look and feel of its
user interface, to adding science-specific parameters to each target to adding custom functions and applications.
All of these options are described :doc:`here<customization/index>`.

Plugins
-------

In addition to the features of the base TOM, we also support a range of optional plugin modules.
These extend the functions of the TOM in various ways that are useful for many users.  Examples include data visualization
tools for specific science goals, and interfaces for observations with additional telescope facilities.
Click :doc:`here<code/plugins>` to browse the list of options.

Support
-------

Looking for help? Want to request a feature? Have questions about Github Issues? Take a look at the :doc:`support guide
<introduction/support>`.

If you just need an idea, checkout out the :doc:`examples<examples>` of existing TOMs built with the TOM Toolkit.

Contributing
------------

The TOM Toolkit is a community-driven project and we welcome feedback and contributions from our users!
If you find an issue, you need help with your TOM, you have a useful idea, or you wrote a module you'd like to be
included in the TOM Toolkit, start with our :doc:`contribution guide <introduction/contributing>`.

Acknowledging the TOM Toolkit
-----------------------------

We hope you find our software useful for your research.  If so, we would be grateful
if you can include a brief acknowledgement in your papers and presentations, for example
"This research made use of `The TOM Toolkit <https://tom-toolkit.readthedocs.io/>`_".
We would also very much appreciate you including a citation to our paper describing
the Toolkit `Street, R.A. et al., 2018, SPIE, 10707, 11 <http://adsabs.harvard.edu/abs/2018SPIE10707E..11S>`_
(to export the BibTeX please click `here <https://ui.adsabs.harvard.edu/abs/2018SPIE10707E..11S/exportcitation>`_).

Acknowledgements
----------------

The TOM Toolkit is managed by Las Cumbres Observatory, with generous
financial support from the `National Science Foundation <https://www.nsf.gov/>`_ grant 2209852.
We are also grateful for support from the `Heising-Simons Foundation
<https://hsfoundation.org>`_ and the `Zegar Family Foundation
<https://sites.google.com/zegarff.org/site>`_ at the start of the project.

Read about the project and the motivations behind it on the :doc:`About page <introduction/about>`.
