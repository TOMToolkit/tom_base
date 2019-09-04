Customizing Data Processing
---------------------------

One of the many goals of the TOM Toolkit is to enable the simplification of the flow of your data from observations. To
that end, there's some built-in functionality that can be overridden to allow your TOM to work for your use case.

To begin, here's a brief look at the part of the structure of the tom_dataproducts app in the TOM Toolkit:

```
tom_dataproducts
├──data_processor.py
├──data_serializers.py
├──hooks.py
└──models.py
```

Let's start with a quick overview of `models.py`. The file contains the Django models for the dataproducts app--in our
case, `DataProduct` and `ReducedDatum`. The `DataProduct` contains information about uploaded or saved `DataProducts`,
such as the file name, file path, and what kind of file it is. The `ReducedDatum` contains individual science data
points that are taken from the `DataProduct` files. Examples of `ReducedDatum` points would be individual photometry
points or individual spectra.

When a user either uploads or saves a `DataProduct` to their TOM, the TOM runs a hook, as described in the
[Custom Code](/advanced/custom_code) section of the documentation. The default version of this hook looks like this:

```python
import json

from .data_processor import DataProcessor
from .data_serializers import SpectrumSerializer
from .models import ReducedDatum, SPECTROSCOPY, PHOTOMETRY

def data_product_post_upload(dp, observation_timestamp, facility):
    processor = DataProcessor()

    if dp.tag == SPECTROSCOPY[0]:
        spectrum = processor.process_spectroscopy(dp, facility)
        serialized_spectrum = SpectrumSerializer().serialize(spectrum)
        ReducedDatum.objects.create(
            target=dp.target,
            data_product=dp,
            data_type=dp.tag,
            timestamp=observation_timestamp,
            value=serialized_spectrum
        )
    elif dp.tag == PHOTOMETRY[0]:
        photometry = processor.process_photometry(dp)
        for time, photometry_datum in photometry.items():
            ReducedDatum.objects.create(
                target=dp.target,
                data_product=dp,
                data_type=dp.tag,
                timestamp=time,
                value=json.dumps(photometry_datum)
            )
```

The basic idea is as follows: depending on the tag of the `DataProduct` passed in, the data in the `DataProduct` is
processed by the `DataProcessor` class into a uniform format. The resulting object, if necessary, is then serialized
by the `SpectrumSerializer` (the default photometry format is already easily serializable) so that it can be stored
in the database as a `ReducedDatum`. Then, the `ReducedDatum` objects are created and stored in the database.

The meat and potatoes of the processing is in the `DataProcessor` class, and the details of that can be seen in the
[source code](https://github.com/TOMToolkit/tom_base/tree/master/tom_dataproducts/data_processor.py). We understand
that the way the data is processed might not work for everyone, and so it's easily customizable.

To do so, it's as simple as creating a custom `DataProcessor` class that inherits from the one in the TOMToolkit. Let's
say most of the DataProcessor code is great, but you want to change how spectra are processed from FITS files:

```python
from tom_dataproducts.data_processor import DataProcessor

class CustomDataProcessor(DataProcessor):

  def _process_spectrum_from_fits(self, data_product, facility):
        # Custom processing here, needs to return a Spectrum1D

        return spectrum
```

Then, just add the path to your `CustomDataProcessor` class file to your TOM settings.py:

```python
...
DATA_PROCESSOR_CLASS = 'mytom.custom_data_processor.CustomDataProcessor'
...
```

As long as the `CustomDataProcessor` returns an object with the same type as the superclass implementation, you won't
need to change anything else. However, if you do have a need to return a different object type, then you can just
override the `SpectrumSerializer` in the `tom_dataproducts.data_serializers.py`. Be careful, because the TOM Toolkit
doesn't have a mechanism to provide a custom serializer, so you'll also need to customize your
`data_product_post_upload` hook. Here's a brief example of a custom serializer:

```python
from tom_dataproducts.data_serializers import SpectrumSerializer

class CustomSpectrumSerializer(SpectrumSerializer):

  def serialize(self, spectrum):
    # convert spectrum into dict

    return json.dumps(spectrum_dict)

  def deserialize(self, spectrum):
    data = json.loads(spectrum) # spectrum is a dict object

    # convert from dict to preferred object type
    return converted_spectrum
```

Then, in your custom hook:

```python
import json

from .models import ReducedDatum, SPECTROSCOPY, PHOTOMETRY

from mytom.custom_data_serializers import CustomSpectrumSerializer
from mytom.custom_data_processor import CustomDataProcessor

def custom_data_product_post_upload(dp, observation_timestamp, facility):
    processor = CustomDataProcessor()

    if dp.tag == SPECTROSCOPY[0]:
        spectrum = processor.process_spectroscopy(dp, facility)
        serialized_spectrum = CustomSpectrumSerializer().serialize(spectrum)
        ReducedDatum.objects.create(
            target=dp.target,
            data_product=dp,
            data_type=dp.tag,
            timestamp=observation_timestamp,
            value=serialized_spectrum
        )
    elif dp.tag == PHOTOMETRY[0]:
        photometry = processor.process_photometry(dp)
        for time, photometry_datum in photometry.items():
            ReducedDatum.objects.create(
                target=dp.target,
                data_product=dp,
                data_type=dp.tag,
                timestamp=time,
                value=json.dumps(photometry_datum)
            )
```

And just like that, your TOM will be running your custom processing code.