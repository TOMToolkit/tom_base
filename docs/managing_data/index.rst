Managing Data
=============

The TOM's Data Models
---------------------

The TOM Toolkit includes two distinct models for data in the ``tom_dataproducts`` module:

* ``DataProduct``: Corresponds to any file containing data, from a FITS, to a PNG, to a CSV. It can optionally be
    associated with a specific observation, and is required to be associated with a target. A ``DataProduct`` can have a
    specified type which can be used to trigger post-save hooks to perform automated process upon ingest.
* ``ReducedDatum``: Refers to a single piece of data - e.g., a spectrum, a single measurement or a set of timeseries
    photometry measurements. It is associated with a target, and optionally with the data product it came from.

The TOM also allows a ``DataProductGroup`` to be defined.  This allows TOM administrators control over which user
groups can access which data products.

Ingesting data into the TOM
---------------------------
Data products for a given target can be uploaded through the ``Manage Data`` tab on the target's detail page, or
programmatically.

.. figure:: /_static/managing_data/data_upload_form.png
   :alt: TOM's data upload form
   :width: 100%
   :align: center

   DataProduct upload form in the TOM's target detail page

If a data product type is specified, then the TOM calls uses post-save hooks to call the corresponding built-in
processing functions found in ``tom_dataproducts/processors``.  The TOM's ``photometry_processor.py`` for example,
reads a photometry data file and ingests the timeseries measurements as ``ReducedDatum``.

It's also possible for users to add their own custom data formats and corresponding specialized processors - see
:doc:`Adding Custom Data Processing <customizing_data_processing>` for more details.

Data Visualization
------------------

The Toolkit includes built-in interactive tools for plotting data types common in astronomy, such as
light curves and spectra.  But it is often useful to customize these for particular science goals.
:doc:`Creating Plots from TOM Data <plotting_data>` describes how to create interactive plots of your data
to display anywhere in your TOM.

Data Sharing
------------

Many users find it valuable to be able to share data from their TOM system with other people, services or directly with
other TOM systems.  The Toolkit includes a number of different data sharing options:

* :doc:`TOM-TOM Direct Sharing <tom_direct_sharing>` - Send and receive data between your TOM and another TOM-Toolkit TOM via an API.

* :doc:`Publish and Subscribe to a Kafka Stream <stream_pub_sub>` - Publish and subscribe to a Kafka stream topic.

* :doc:`Setting up Continuous Sharing of a target's data to a TOM or Kafka stream <continuous_sharing>` - Set up continuous sharing of a Target's data products.

Survey data on a Target
-----------------------

Archival data can be a valuable resource for understanding its nature and behaviour.  These include data archives, which
hold source catalogs, photometry, spectroscopy and imaging data in many wavelengths, as well as forced photometry
services.  These are offered by a number of surveys, to enable users to search for precursor observations.

The TOM include a number of built-in single-target data service query functions to allow the user to harvest data
for a given object from surveys including ATLAS and Pan-STARRS.

To learn about these functions, and how to add a new service to your TOM, see
:doc:`Integrating Single-Target Data Service Queries <single_target_data_service>`.
