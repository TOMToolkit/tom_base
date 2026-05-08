TOM Toolkit Plugins
===================

We aim to keep the TOM as lightweight and flexible as possible, and we 
recognize that every team has their own science goals and often need 
different functions.  These often come with added dependencies.  

Rather than require users to support all dependencies from all possible 
functions, we support a range of optional plugin modules for the Toolkit. 
These range from adding the ability to interface with additional
observatories and catalogs, to providing additional plotting or data analytics functionality.

tom_hermes
----------

`Github link <https://github.com/TOMToolkit/tom_hermes>`_

The `Hermes <https://hermes.lco.global>`_ service provides a archive of
astronomical alerts.  This plugin allows TOM users to query Hermes and share
data with the service.  

tom_fink
--------

`Github link <https://github.com/TOMToolkit/tom_fink>`_

`Fink <https://fink-broker.org/>`_ is an alert broker service.  This plugin
enables users to query this service and harvest alert information. 

tom_antares
-----------

`Github link <https://github.com/TOMToolkit/tom_antares>`_

This plugin adds support for querying the `ANTARES <https://antares.noirlab.edu/>`_ broker for targets of interest.

tom_app_template
----------------

`Github link <https://github.com/TOMToolkit/tom_app_template>`_

This repository is designed to provide a starting template for TOM users 
wishing to develop their own TOM app. This app contains all of the basic workflows, 
directory structure, testing infrastructure, and instructions you will need to get started.

tom_jpl
-------

`Github link <https://github.com/TOMToolkit/tom_jpl>`_

The Jet Propulsion Laboratory provides a number of services supporting 
Solar System science.  This plugin provides a TOM interface to JPL's 
`SCOUT <https://cneos.jpl.nasa.gov/scout/intro.html>`_ service.

tom_eso
-------

`Github link <https://github.com/TOMToolkit/tom_eso>`_

This plugin enables users to compose and submit observation requests to 
telescopes at the `European Southern Observatory <https://www.eso.org/public/>`_.

tom_regions
-----------

`Github link <https://github.com/TOMToolkit/tom_regions>`_

This plugin allows a TOM to store sky regions defined from Multi-Order 
Coverage maps. 

tom_registration
----------------

`Github link <https://github.com/TOMToolkit/tom_registration>`_

This plugin introduces support for two TOM registration
workflows including an open registration, and a registration that requires administrator approval.

tom_tns
-------

`Github link <https://github.com/TOMToolkit/tom_tns>`_

This plugin enables TOMs to report transient classifications to 
the `Transient Name Server <https://www.wis-tns.org/>`_.

tom_alertstreams
----------------

`Github link <https://github.com/TOMToolkit/tom_alertstreams>`_

Apache Kafka is widely used in astrophysics for the dissemination of 
alert packages.  This plugin enables a TOM system to listen to user-configured 
alerts streams. 

tom_demoapp
-----------

`Github link <https://github.com/TOMToolkit/tom_demoap>`_

This TOM application is not designed to be installed by users, but instead act 
as a development and demonstration app for users wishing to integrate their 
own TOM applications with the base TOM toolkit. The code itself serves as example, 
while the `wiki <https://github.com/TOMToolkit/tom_demoapp/wiki>`_ gives a menu of existing integration points.

tom_nonlocalizedevents
----------------------

`Github link <https://github.com/TOMToolkit/tom_nonlocalizedevents>`_

Various events in astrophysics are hard to localize, for example gravitational wave
 or neutrino detections.  This app allows the TOM to recognize that a
given event may be associated with a number of candidates, and provides 
custom views designed to support this workflow.

tom_swift
---------

`Github link <https://github.com/TOMToolkit/tom_swift>`_

The `Neil Gehrels Swift Observatory <https://swift.gsfc.nasa.gov/>`_ is a space telescope offering
UV/Visible and X-ray instrumentation and rapid response capabilities.  This plugin 
enables TOM users to submit requests for Target of Opportunity observations 
with this spacecraft. 

tom_classifications
-------------------

`Github link <https://github.com/TOMToolkit/tom_classifications>`_

This app provides a number of data visualization tools for inspecting alert 
data from multiple brokers. 

tom_keck
--------

`Github link <https://github.com/TOMToolkit/tom_keck>`_

Application to enable requests for Target of Opportunity observations 
to be submitted to the `Keck Observatories <https://keckobservatory.org/>`_.
Note: to be integrated with `AEONlib <https://github.com/AEONplus/AEONlib>`_.

tom-lt
------

`Github link <https://github.com/TOMToolkit/tom_lt>`_

This module provides the ability to submit observations to the 
`Liverpool Telescope <https://telescope.livjm.ac.uk/>`_ Phase 2 system. It is in a very alpha
state, with little error handling and minimal instrument options, but can successfully submit well-formed observation
requests.

tom-toolkit_component_lib
-------------------------

`Github link <https://github.com/TOMToolkit/tom-toolkit-component-lib>`_

Demonstration of how Javascript front-end components can be integrated with 
a TOM. 

tom_dash
--------

`Github link <https://github.com/TOMToolkit/tom_dash>`_

This module demonstrates how `Plotly-Dash <https://dash.plotly.com/>`_ components can be added to a
TOM for data exploration and visualization. 

tom_gemini_community
--------------------

`Github link <https://github.com/TOMToolkit/tom_gemini_community>`_

TOM module to enable observations to be submitted to the 
`Gemini Telescope's <http://www.gemini.edu/>`_ Phase 2 system.

tom_nonsidereal_airmass
-----------------------

`Github link <https://github.com/TOMToolkit/tom_nonsidereal_airmass>`_

This plugin provides a templatetag that supports plotting for non-sidereal objects. The plugin is fully supported by the TOM Toolkit team; however,
non-sidereal visibility calculations require the PyEphem library, which is minimally supported while its successor
is in development. The library used for the TOM Toolkit sidereal visibility, astroplan, does not yet support
non-sidereal visibility calculations.

tom_publications
----------------

`Github link <https://github.com/TOMToolkit/tom_publications>`_

This application prototyped tools to enable users to output latex-formatted 
data from their TOM system. 

herokutom
---------

`Github link <https://github.com/TOMToolkit/herokutom>`_

This repository demonstrates how a TOM system can be deployed to a public 
server using the `Heroku platform <https://www.heroku.com/>`_.

Archived plugins
----------------

The following plugins are available but not currently supported.  In some 
cases this is because the functionality has been integrated with the 
base Toolkit. 

tom_alerts_dash
---------------

`Github link <https://github.com/TOMToolkit/tom_alerts_dash>`_

This plugin adds responsive ReactJS views to the
`tom_alerts` module for supported brokers.  The `tom_alerts` module has been superseded 
by tom_dataservices in v3.0.0.  

dockertom
---------

`Github link <https://github.com/TOMToolkit/dockertom>`_

This repository demonstrates how to package a TOM system in a docker container, 
which is often required for deployment.  

tom_scimma
----------

`Github link <https://github.com/TOMToolkit/tom_scimma>`_

This app enables a TOM to subscribe to the Hopskotch alert stream developed 
by the Scalable Cyberinfrastructure to support Multi‑Messenger Astrophysics 
(`SCiMMA <https://scimma.org/>`_) project.
