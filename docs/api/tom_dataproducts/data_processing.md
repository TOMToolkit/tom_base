# Data Processing

The TOM is configured with built-in data processing on the upload of Data Products. This processing is broken up into
three components.

* ``tom_dataproducts.data_processor.run_data_processor``
* ``tom_dataproducts.data_processor.DataProcessor``
* ``tom_dataproducts.data_serializers``

The ``DataProductUploadView`` calls ``run_data_processor`` upon saving the ``DataProduct``. ``run_data_processor``
instantiates the ``DATA_PROCESSOR_CLASS``, which can be specified in ``settings.py``. ``run_data_processor`` then
processes the uploaded ``DataProduct`` based on the tag value, which can either be Photometry or Spectroscopy.

In the case of spectra, the default behavior is that ``DataProduct`` is converted into a ``specutils.Spectrum1D`` from
either a CSV or a FITS file. The spectrum is multiplied by the flux constant of the facility it was taken at, or not
multiplied. The ``Spectrum1D`` is then serialized into JSON for database via the ``SpectrumSerializer``.

For photometry, the default behavior is simply to read the CSV and convert it to JSON for database storage.

Data Serializers
----------------

.. autoclass:: tom_dataproducts.processors.data_serializers.SpectrumSerializer
    :members:


Data Processors
---------------

.. autofunction:: tom_dataproducts.data_processor.run_data_processor

.. autoclass:: tom_dataproducts.data_processor.DataProcessor
    :members:
    :private-members:
    :member-order: bysource
