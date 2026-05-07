Observing Facilities and Observations
=====================================

One of a TOM's most powerful features is to enable astronomers to directly request observations from telescope facilities.
With this capability becoming more and more common among observatories, TOMs can be used to easily coordinate observations
across a number of telescopes.  Observing programs can also scripted, so that the TOM can automatically observe
targets selected according to pre-defined criteria and with observations determined by a pre-defined strategy.

Built-in Observing Facilities
-----------------------------

The TOM includes built-in modules that provide interfaces to a number of telescopes including:

* `Las Cumbres Observatory 0.4m, 1m and 2m telescope networks <https://lco.global>`_
* `4.1m Southern Astrophysical Research (SOAR) Telescope <https://noirlab.edu/public/programs/ctio/soar-telescope/>`_
* `8m Gemini Telescopes North and South <https://www.gemini.edu/>`_
* `4m Víctor M. Blanco Telescope <https://noirlab.edu/public/programs/ctio/victor-blanco-4m-telescope/>`_

These modules enable users to compose and submit requests for observations, and to calculate target visibility from
these observing sites.  Data products resulting from submitted observations can also be retrieved.

Detailed information on these modules can be found here:
:doc:`Facility Modules <../api/tom_observations/facilities>` - Take a look at the supported facilities.

:doc:`Observation Views <../api/tom_observations/views>` - Familiarize yourself with the available Observation Views.


Additional Telescope Facilities
-------------------------------

The Toolkit also has a number of optional plugin modules providing interfaces to other telescopes, including:

* `2m Liverpool Telescope <https://telescope.livjm.ac.uk/>`_
* `Telescopes at the European Southern Observatory <https://www.eso.org/public/>`_
* `Neil Gehrels Swift Observatory <https://science.nasa.gov/mission/swift/spacecraft/>`_

For more information about the plugin modules, see :doc:`Plugins </code/plugins>`.

Facilities
----------

The TOM's ``tom_observations`` module also has a database table (model) for telescope facilities where users can store
general information about telescopes, including the location of the telescope site(s) or orbits, wavelength range, etc.
This information is used by the TOM when calculating target visibility, even if the telescope doesn't accept programmatic
submission of observations.

A TOM administrator can add facilities to this table using the TOM's admin interface.

Adding Telescope Modules to the TOM
-----------------------------------

Modules can be added to enable the submission of observations to additional telescope facilities.
For telescopes using LCO's `Observatory Control System <https://observatorycontrolsystem.github.io/>`_ software,
:doc:`Customizing an OCS Facility and its Forms <customize_ocs_facility>` describes how to customize the facility and
its observation forms to add new fields and behaviour.

:doc:`Building a TOM Observation Facility Module <observation_module>` describes how to build a module for any telescope
that allows the programmatic submission of observations.

We encourage users with custom telescope module to submit a pull request through Github to the TOM Toolkit, to share
the capability with other users.

Observing Programs
------------------

`Programmatically Submitting Observations <../common/scripts.html#creating-observations-programmatically>`__

:doc:`Cadence and Observing Strategies <strategies>` - Learn how to build cadence strategies that submit observations based on 
the result of prior observations, as well as how to leverage observing templates to submit observations with fewer clicks.


Finding visible targets
-----------------------

:doc:`Selecting Targets <selecting_targets_for_facility>` - Display a selection of targets for a specific observing facility.


Observation Records
-------------------

:doc:`Observation Models <../api/tom_observations/models>` - Learn about the models used to store observation data.
