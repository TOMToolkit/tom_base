Data Services
=============

.. toctree::
  :maxdepth: 2
  :caption: Table of Contents
  :hidden:

  Add a data service <create_dataservice>
  ALeRCE: ZTF and LSST <alerce>
  Available data services <../api/tom_dataservices/data_services>
  Data service views <../api/tom_dataservices/views>

What is a Data Service Module?
-------------------------------

A TOM Toolkit Data Service Module contains the logic for querying a remote broker or catalog service
(e.g `ANTARES <https://antares.noirlab.edu>`_), and transforming the returned data into TOM Toolkit Targets and Reduced Datums.

:doc:`Creating a new Data Service <create_dataservice>` - Learn how to add a custom data service module to query for targets and data from your favorite brokers and catalogs.

:doc:`Data Service Modules <../api/tom_dataservices/data_services>` - Take a look at the supported Data Services.

:doc:`ALeRCE: ZTF and LSST <alerce>` - Search ALeRCE for ZTF and LSST objects, including LSST asteroids, and ingest their light curves.

:doc:`Data Service Views <../api/tom_dataservices/views>` - Familiarize yourself with the available Data Service Views.
