TOM Workflow
------------

Targets 
~~~~~~~

Targets are the central entity of the TOM Toolkit. Most functionality in
the toolkit requires a target as they are the object of study. A target
represents an astronomical object (star, galaxy, asteroid, etc) and is
usually represented using coordinates on the sky along with other meta
data.

Creating Targets 
^^^^^^^^^^^^^^^^

The TOM Toolkit provides a variety of methods for importing astronomical
targets into the TOM:

.. image:: /_static/target_sources.png

-  The Alert Module provides the functionality to create targets from
   alert brokers such as ``MARS <https://mars.lco.global>``\ \_\_ and
   ``ANTARES <https://antares.noirlab.edu/>``\ \__. These brokers generally
   provide alerts from transient phenomena as soon as they happen, and a
   scientist who is interested in studying these phenomena can import
   these alerts as targets into their TOM to study in real time.

-  Online catalogs such as SIMBAD and the JPL Horizons contain
   information on millions of existing astronomical objects. If a
   scientist wishes to study one of these existing objects, they can
   query these catalogs directly from the TOM and use the returned data
   to create TOM Targets.

-  Manual entry/bulk upload allows a scientist to create targets that
   aren’t known by any of the existing catalogs or use more precise
   information that they know of.

Observations 
~~~~~~~~~~~~

After creating targets, the scientist needs to collect data on these
targets. The TOM Observing module provides an interface to several
observatories for which observations can be requested.

Requesting Observations 
^^^^^^^^^^^^^^^^^^^^^^^

Using the TOM Observation module, scientists can request observations of
their targets to one or many different observatories. Since the
observing module has access to targets stored in the TOM database it can
automatically fill in many of the observing parameters required by
observing facilities, greatly reducing the workload of the scientist.
The observing module also provides a common interface, removing the need
of the scientist to navigate many different online systems to request
observations.

Observations can also be requested in a completely automated manner,
which is particularly useful for rapid response time domain follow-up
programs.

.. image:: /_static/common_interface.png

Observation Status 
^^^^^^^^^^^^^^^^^^

Once an observation for a target is created it’s status is kept up to
date within the TOM. When the status of an observation request at an
observatory changes (failed, completed, postponed, etc) the scientist
may be notified by the TOM.

Data 
~~~~

The ultimate goal of the TOM toolkit is to collect and organize data.
The TOM data module provides several methods for obtaining data, the
most obvious being from completed observations. Scientists can also
upload any data they’d like to associate with their targets as well.

Data Processing 
^^^^^^^^^^^^^^^

The TOM toolkit provides a framework to write custom code to interact
with the data the TOM obtains (among other things). These are called
“hooks” and they can be used by scientists to write custom image
pipelines, data quality checks, or to hook into entirely different
systems. For example: if a scientist has existing code that checks
images of microlensed stars for exoplanets, they may hook the code into
the TOM toolkit directly to run whenever new data is acquired.

Downloading Data 
^^^^^^^^^^^^^^^^

Data is stored in the TOM toolkit by default, but many scientists may
want to download the data somewhere else to do offline processing.
Scientists can easily download data to their local machines, and the
data module by default stores all it’s data on a local file system.
However, it can be customized to store data on cloud services, like
Amazon S3, when desired.
