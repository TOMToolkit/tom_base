Brokers
=======

.. toctree::
  :maxdepth: 2
  :hidden:

  create_broker
  create_dash_broker
  ../api/tom_alerts/brokers
  ../api/tom_alerts/views


What is an Alert Broker Module?
-------------------------------

A TOM Toolkit Alert Broker Module is an object which contains the logic for querying a remote broker
(e.g `MARS <https://mars.lco.global>`_), and transforming the returned data into TOM Toolkit Targets.

:doc:`Creating an Alert Broker <create_broker>` - Learn how to add a custom broker module to query for targets from your favorite broker.

:doc:`Creating a Dash Alert Broker <create_dash_broker>` - Add a responsive broker module to browse alerts using Plotly Dash.

:doc:`Broker Modules <../api/tom_alerts/brokers>` - Take a look at the supported brokers.

:doc:`Broker Views <../api/tom_alerts/views>` - Familiarize yourself with the available Broker Views.
