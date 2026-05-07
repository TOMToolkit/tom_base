Dataservices
============

There are many sources of data in astrophysics, including alert brokers, data archives, data sharing facilities and
forced photometry services.  Many services offer a number of functions.  TOM's dataservices module provides interfaces to
enable users to query these services and retrieve data from them for further analysis in the TOM.

Built-in Dataservices
---------------------
The Toolkit includes built-in modules to query widely-used public services, including:

* `Simbad <http://simbad.u-strasbg.fr/Simbad>`__
* `The Transient Name Server <https://www.wis-tns.org/>`__
* `ANTARES alert broker <https://antares.noirlab.edu/>`__
* `Fink alert broker <https://fink-broker.org/>`__
* `ALeRCE alert broker <https://science.alerce.online/>`__
* `Hermes <https://hermes.lco.global>`__
* `JPL SCOUT <https://cneos.jpl.nasa.gov/scout/>`__

More information on these interfaces is summarized in :doc:`Broker Modules </api/tom_alerts/brokers>`, and
:doc:`Broker Views </api/tom_alerts/views>` describes the views available.

Adding Dataservices
-------------------

The Toolkit is designed to be extensible and we welcome contributed modules.  If you're interested
in developing a dataservice for your own science, here are some resources to get you started.

:doc:`Creating an Alert Broker <create_broker>` - Learn how to add a custom broker module to query for targets from your favorite broker.

:doc:`Creating a Dash Alert Broker <create_dash_broker>` - Add a responsive broker module to browse alerts using Plotly Dash.

:doc:`Create Data Service <create_dataservice>` - Walk through the creation of your own Data Service.
