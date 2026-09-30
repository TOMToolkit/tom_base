Managing Data
=============

.. toctree::
  :maxdepth: 2
  :caption: Table of Contents
  :hidden:

  Custom data processing <customizing_data_processing>
  TOM-TOM data sharing <tom_direct_sharing>
  Continuous data sharing <continuous_sharing>
  Streaming data <stream_pub_sub>
  Single-target data service <single_target_data_service>
  Accessing data through the REST API <accessing_data_through_REST_API>
  Visualizing data <plotting_data>

The TOM's Data Models
---------------------

The TOM Toolkit's' ``tom_dataproducts`` module recognizes a distinction between a *data product* and a *datum*:

* ``DataProduct``: Corresponds to any file containing data, from a FITS, to a PNG, to a CSV. It can optionally be
    associated with a specific observation, and is required to be associated with a target. A ``DataProduct`` can have a
    specified type which can be used to trigger post-save hooks to perform automated process upon ingest.
* ``*ReducedDatum`` (multiple types): Refers to a single piece of data - e.g., a spectrum, a single measurement or a set of timeseries
    photometry measurements. It is associated with a target, and optionally with the data product it came from.

The TOM also allows a ``DataProductGroup`` to be defined.  This allows TOM administrators control over which user
groups can access which data products.

There are a number models to describe data types common in astronomy.

* ``PhotometryReducedDatum``: Designed for measurements of brightness, this model has attributes ``brightness, brightness_error, limit, unit, bandpass`` and ``exposure_time``.  It is designed to support both measured values and brightness limits for cases where direct measurement is not possible.
* ``SpectroscopyReducedDatum``: Designed for data with an associated wavelength, this model records the instrument ``setup`` and ``exposure_time`` in addition to the ``wavelength, flux, error``.  The parameters ``flux_unit, wavelength_unit`` allow different spectral units to be stored.
* ``AstrometryReducedDatum``: Designed for objects with measured movement, this model records attributes ``ra, dec, ra_error, dec_error, ra_error_units, dec_error_units``.
* ``ReducedDatum``: Designed to be a general-purpose model to store data not represented by the other models. It's attribute is ``data_type``.

All of the models inherit from the base class ``ReducedDatumCommon``, which has attributes common to all data,
including ``timestamp``.  Foreign keys associate each datum with ``Target`` and ``DataProduct`` model entries.  The
``value`` attribute is a JSON field which can store any dictionary of data and is designed to provide a
flexible means to store any further information the user requires. The ``telescope, instrument,
source_name, source_location`` and ``reduction_version`` attribues are character fields where users can
record the origin of the data.

**Older versions**: These datum types were introduced in
`TOM Toolkit v3.0.0 <https://github.com/TOMToolkit/tom_base/releases#release-3.0.0>`_;
older TOMs supported just the generic ReducedDatum.  If you are upgrading an older TOM, please see
:doc:`these instructions <../introduction/updating>`.

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

Data Validation
---------------
Before any ``*ReducedDatum`` is stored in the TOM it is validated to avoid duplicating data entries.
A ``ValidationError`` will be raised if the new datum has the same ``data_type``, ``timestamp`` and ``value``,
as an existing datum and is associated with the same ``target``.

When performing a ``bulk_create`` of multiple ``*ReducedDatums ``, a ``ValidationError`` can cause the
whole batch to be aborted.  If you just wish to skip duplicate rows and ingest only new entries, you can
use ``ignore_conflicts`` with most database types:

``PhotometryReducedDatum.objects.bulk_create(reduced_datums_list, ignore_conflicts=True)``

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
