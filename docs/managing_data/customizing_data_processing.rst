Customizing Data Processing
---------------------------

One of the many goals of the TOM Toolkit is to enable the simplification
of the flow of your data from observations. To that end, there’s some
built-in functionality that can be overridden to allow your TOM to work
for your use case.

To begin, here’s a brief look at part of the structure of the
tom_dataproducts app in the TOM Toolkit:

::

   tom_dataproducts
   ├──hooks.py
   ├──models.py
   └──processors
      ├──data_serializers.py
      ├──photometry_processor.py
      └──spectroscopy_processor.py

Let’s start with a quick overview of ``models.py``. The file contains
the Django models for the dataproducts app–in our case, ``DataProduct``
and ``ReducedDatum``. The ``DataProduct`` contains information about
uploaded or saved ``DataProducts``, such as the file name, file path,
and what kind of file it is. The ``ReducedDatum`` contains individual
science data points that are taken from the ``DataProduct`` files.
Examples of ``ReducedDatum`` points would be individual photometry
points or individual spectra.

Each ``DataProduct`` also has a ``data_product_type``. The
``data_product_type`` is simply a description of what the file is, more
or less, and is customizable. The list of supported
``data_product_type``\ s is maintained in ``settings.py``:

.. code:: python

   # Define the valid data product types for your TOM. Be careful when removing items, as previously valid types will no
   # longer be valid, and may cause issues unless the offending records are modified.
   DATA_PRODUCT_TYPES = {
       'photometry': ('photometry', 'Photometry'),
       'fits_file': ('fits_file', 'FITS File'),
       'spectroscopy': ('spectroscopy', 'Spectroscopy'),
       'image_file': ('image_file', 'Image File')
   }

In order to add new data product types, simply add a new key/value pair,
with the value being a 2-tuple. The first tuple item is the database
value, and the second is the display value.

All data products are automatically “processed” on upload, as well. Of
course, that can mean different things to different TOMs! The TOM has
two built-in data processors, both of which simply ingest the data into
the database, and those are also specified in ``settings.py``:

.. code:: python

   DATA_PROCESSORS = {
       'photometry': 'tom_dataproducts.processors.photometry_processor.PhotometryProcessor',
       'spectroscopy': 'tom_dataproducts.processors.spectroscopy_processor.SpectroscopyProcessor',
   }

When a user either uploads a ``DataProduct`` to their TOM, the TOM runs
``process_data()`` from the corresponding ``DataProcessor`` subclass
specified in ``DATA_PROCESSORS`` seen above. To illustrate, this is the
base ``DataProcessor`` class:

.. code:: python

   import mimetypes

   ...

   class DataProcessor():

       FITS_MIMETYPES = ['image/fits', 'application/fits']
       PLAINTEXT_MIMETYPES = ['text/plain', 'text/csv']

       mimetypes.add_type('image/fits', '.fits')
       mimetypes.add_type('image/fits', '.fz')
       mimetypes.add_type('application/fits', '.fits')
       mimetypes.add_type('application/fits', '.fz')

       def process_data(self, data_product):
           pass

Now let’s look at the built-in data processors. First, let’s check out
the ``PhotometryProcessor``, which inherits from ``DataProcessor``:

.. code:: python

   class PhotometryProcessor(DataProcessor):

       def process_data(self, data_product):
           mimetype = mimetypes.guess_type(data_product.data.path)[0]
           if mimetype in self.PLAINTEXT_MIMETYPES:
               photometry = self._process_photometry_from_plaintext(data_product)
               return [(datum.pop('timestamp'), json.dumps(datum)) for datum in photometry]
           else:
               raise InvalidFileFormatException('Unsupported file type')

This class has an implementation of ``process_data()`` from the
superclass ``DataProcessor``. The implementation calls an internal
method ``_process_photometry_from_plaintext()``, which return a ``list``
of ``dict``\ s. Each dict contains the values for the timestamp,
magnitude, filter, and error for that photometry point. The list is then
transformed into a list of 2-tuples, with the first value being the
photometry timestamp, and the second being the JSON-ified remaining
values.

Next, let’s look at the ``SpectroscopyProcessor``:

.. code:: python

   class SpectroscopyProcessor(DataProcessor):

       DEFAULT_WAVELENGTH_UNITS = units.angstrom
       DEFAULT_FLUX_CONSTANT = units.erg / units.cm ** 2 / units.second / units.angstrom

       def process_data(self, data_product):

           mimetype = mimetypes.guess_type(data_product.data.path)[0]
           if mimetype in self.FITS_MIMETYPES:
               spectrum, obs_date = self._process_spectrum_from_fits(data_product)
           elif mimetype in self.PLAINTEXT_MIMETYPES:
               spectrum, obs_date = self._process_spectrum_from_plaintext(data_product)
           else:
               raise InvalidFileFormatException('Unsupported file type')

           serialized_spectrum = SpectrumSerializer().serialize(spectrum)

           return [(obs_date, serialized_spectrum)]

Just like the ``PhotometryProcessor``, this class inherits from
``DataProcessor`` and implements ``process_data()``. This is a
requirement for a custom DataProcessor! This ``process_data()`` method
handles two file types, unlike the previous example, each of which calls
an internal method that returns a ``Spectrum1D`` object. Again, like the
``PhotometryProcessor``, a list of 2-tuples is created, with the first
value being the timestamp, and the second being the JSON spectrum.

You may be wondering why these two methods return lists of 2-tuples,
especially when the ``SpectroscopyProcessor`` only returns a list of
length one. The rationale is to ensure that you, the TOM user, shouldn’t
have to worry about the database insertion, so the internal logic
handles that aspect, and it can do so whether you return one data point
or many data points.

For a custom ``DataProcessor``, there are just a few required steps. The
first is to create a class that implements ``DataProcessor``, like so:

.. code:: python

   from tom_dataproducts.data_processor import DataProcessor


   class MyDataProcessor(DataProcessor):

       def process_data(self, data_product):
           # custom data processing here

           return [(timestamp1, json1), (timestamp2, json2), ..., (timestampN, dictN)]

Let’s say that this file lives at ``mytom/my_data_processor.py``. Now
the processor needs to be added to ``DATA_PROCESSORS``, and it can
either process a new data product type, or replace an existing one.
Let’s replace spectroscopy:

.. code:: python

   DATA_PROCESSORS = {
       'photometry': 'tom_dataproducts.processors.photometry_processor.PhotometryProcessor',
       'spectroscopy': 'mytom.my_data_processor.MyDataProcessor',
   }

And that’s it! Now your TOM will run the data processing specific to
your case instead of the default one.
