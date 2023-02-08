Customizing an OCS Facility
---------------------------

The `Observatory Control System <https://observatorycontrolsystem.github.io/>`_ (OCS) is an open-source
software system whose goal is to bring the benefits of API-driven observing to the astronomical
community. `Las Cumbres Observatory <https://lco.global/>`_ successfully operates a global network of
20+ robotic telescopes using the OCS.

The OCS Facility module for the TOM Toolkit should work for an OCS based observatory
by setting the proper settings in your TOM's ``settings.py``.

The base OCS Facility implementation
supports showing all the instruments that are schedulable, along with all of their potential
`optical_elements` as defined within your OCS configuration database.

.. code-block:: python
 :linenos:

    # settings.py
    TOM_FACILITY_CLASSES = [
        'tom_observations.facilities.ocs.OCSFacility',
        ...
    ]
    FACILITIES = {
        'OCS': {
            'portal_url': 'your-ocs-observation-portal-base-url',
            'api_key': 'your-ocs-account-api-token',
            'archive_url': 'your-ocs-archive-api-base-url',
            'max_configurations': 3,  # How many configurations are present on the form
            'max_instrument_configs': 3  # How many instrument configurations are present on the form
        },
        ...
    }

This should work for simple observatories with a single available instrument, but once you have
multiple telescopes and instruments, you will likely want to subclass the OCS implementation and
create your own facility. This will allow you to create specific form pages for each instrument
you provide, which provides the opportunity to customize those forms for instrument specific features.
We will walk you through an example, custom OCS Facility and observing form below. We also show several
key ways in which they could be customized to fit your needs.

This guide assumes you have followed the `getting
started </introduction/getting_started>`__ guide and have a working TOM
up and running.

Create a new OCS based Observing Facility module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Many methods of customizing the TOM Toolkit involve inheriting/extending
existing functionality. This time will be no different: you'll crate a
new observation module that inherits the existing functionality from
``tom_observations.facilities.ocs.OCSFacility``.

First, create a python file somewhere in your project to house your new
module. For example, it could live next to your ``settings.py``, or if
you’ve started a new app, it could live there. It doesn’t really matter,
as long as it’s located somewhere in your project:

::

   touch mytom/mytom/custom_ocs.py

Now add some code to this file to create a new observation module:

.. code-block:: python
 :linenos:


    # custom_ocs.py
    from tom_observations.facilities.ocs import OCSFacility


    class CustomOCSFacility(OCSFacility):
        name = 'CustomOCS'
        observation_forms = {
            'Instrument1': Instrument1ObservationForm,
            'Spectra': SpectraObservationForm    
        }

So what does the above code do?

1. Line 2 imports the OCSFacility that is already shipped with the TOM
   Toolkit. You want this class because it contains functionality you will
   re-use in your own implementation.
2. Line 5 defines a new class named ``CustomOCSFacility`` that
   inherits from ``OCSFacility``.
3. Line 6 sets the name attribute of this class to ``CustomOCS``. This is
   how the TOM facilities modules knows how to reference your facility, and
   therefor should be unique.
4. Line 7 defines two new Observation forms, which will be implemented in
   the next section.

Now you need to tell your TOM where to find your new module so you can use
it to submit observations. Add (or edit) the following lines in your ``settings.py``:

.. code-block:: python
 :linenos:

    # settings.py
    TOM_FACILITY_CLASSES = [
        'mytom.custom_ocs.CustomOCSFacility',
        ...
    ]

This code lists all of the observation modules that should be available
to your TOM.

With that done, go to any target in your TOM and you should see your new
module in the list. But right now, if you click on your `CustomOCS` module,
you will get an error because the specific forms you referenced do not
exist yet. Those forms will be added the next two sections.

Create a new OCS based observing form for a specific instrument
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Let's assume your observatory has several instruments available, each with a varying set
of extra parameters that can be set by the user. In this section, you will create
a customized form specific to instrument `Instrument1`, and add some custom fields
to its `instrument_configuration` layout. We will be adding a `readout_mode` dropdown
since your instrument has many readout modes, and a `defocus` value, since your science
requires setting how defocused the instrument should be for each exposure. First, start
by subclassing the base class of the full OCS observation form:
``tom_observations.facilities.ocs.OCSFullObservationForm``.

.. code-block:: python
 :linenos:

    # custom_ocs.py
    from tom_observations.facilities.ocs import OCSFullObservationForm, OCSFacility
    from django import forms


    class Instrument1InstrumentConfigLayout(OCSInstrumentConfigLayout):
        def get_final_ic_items(self, config_instance, instance):
            # This piece of layout will be added at the end of the base Instrument Config
            # Layout. There is also a method that could be overridden to add to the beginning,
            # Or you can override _get_ic_layout to completely change the layout.
            return (
                Div(
                    Div(
                        f'c_{config_instance}_ic_{instance}_readout_mode',
                        css_class='col'
                    ),
                    Div(
                        f'c_{config_instance}_ic_{instance}_defocus',
                        css_class='col'
                    ),
                    css_class='form-row'
                )
            )


    class Instrument1ObservationForm(OCSFullObservationForm):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # The init method is where you will define fields, since the field names are
            # set based on the number of configurations and instrument configurations our
            # form supports. You can also remove base fields here if you don't want them
            # in your form. 
            for j in range(self.facility_settings.get_setting('max_configurations')):
                for i in range(self.facility_settings.get_setting('max_instrument_configs')):
                    self.fields[f'c_{j+1}_ic_{i+1}_defocus'] = forms.IntegerField(
                        min_value=0, max_value=10, label='Defocus', initial=0, required=False,
                        help_text='Defocus for instrument in mm')
                    self.fields[f'c_{j+1}_ic_{i+1}_readout_mode'] = forms.ChoiceField(
                        choices=self.filter_choices_for_group(oe_group_plural), required=False,
                        label='Readout Mode')

        def get_instruments(self):
            # Override this method to filter down the set of instruments available
            # This is used to define all other configuration fields as well, based on the
            # instrument set available for this form.
            instruments = super().get_instruments()
            return {
                code: instrument for (code, instrument) in instruments.items() if (
                    'IMAGE' == instrument['type'] and 'INSTRUMENT1' == code.upper())
            }

        def configuration_type_choices(self):
            # Override this method if you only want to expose a subset of the available
            # configuration types to users.
            return [('EXPOSE', 'Exposure'), ('REPEAT_EXPOSE', 'Exposure Sequence')]


        def form_name(self):
            # This must be a unique identifier for the form.
            return 'Instrument1'

        def instrument_config_layout_class(self):
            # This method sets the Instrument Config Layout class. Here you are setting
            # your custom class defined above which adds your two new fields to the form.
            return Instrument1InstrumentConfigLayout

        def _build_instrument_config(self, instrument_type, configuration_id, id):
            # This is called when submitting or validating the form, and it constructs the 
            # payload to send to the OCS observation portal. You can get the payload with 
            # base fields and then add your new fields in here.
            instrument_config = super()._build_instrument_config(instrument_type, configuration_id, id)
            if self.cleaned_data.get(f'c_{j+1}_ic_{i+1}_readout_mode'):
                instrument_config['mode'] = self.cleaned_data[f'c_{j+1}_ic_{i+1}_readout_mode']
            if self.cleaned_data.get(f'c_{j+1}_ic_{i+1}_defocus'):
                if 'extra_params' not in instrument_config:
                    instrument_config['extra_params'] = {}
                instrument_config['extra_params']['defocus'] = self.cleaned_data[f'c_{j+1}_ic_{i+1}_defocus']
            return instrument_config

The above code should define a form which only has one specific instrument type, and adds two new
fields to the `instrument_config` section of the form. Pay careful attention to the comments within
the code block for a description of why each section is overriden.


Create a new OCS based observing form for spectrographs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Now let's assume your observatory has multiple spectrographs, and each one has several different
settings for acquisition. In this section, we will create another custom OCS observation form,
this time tailoring it to spectrograph instruments and adding additional fields for acquisition
parameters: acquisition `mode`, `exposure_time` and a `guide_star`. The guide star will be a
target present in your TOM's target database. You will start by subclassing the base class of
the full OCS observation form: ``tom_observations.facilities.ocs.OCSFullObservationForm``.

.. code-block:: python
 :linenos:

    # custom_ocs.py
    from tom_observations.facilities.ocs import OCSFullObservationForm, OCSFacility
    from django import forms


    class SpectrographConfigurationLayout(OCSConfigurationLayout):
        def get_initial_accordion_items(self, instance):
            # This piece of layout will be added at the beginning of the base Configuration Layout
            # accordion group. There is also a method that could be overridden to add to the end of the
            # accordion group, or you can override _get_config_layout to completely change the layout.
            return (
                Div(
                    Div(
                        f'c_{instance}_acquisition_mode',
                        css_class='col'
                    ),
                    Div(
                        f'c_{instance}_exposure_time',
                        css_class='col'
                    ),
                    css_class='form-row'
                ),
                Div(
                    Div(
                        f'c_{instance}_acquisition_guide_star',
                        css_class='col'
                    ),
                    css_class='form-row'
                )
            )       
            
            def get_final_ic_items(self, config_instance, instance):
            # This piece of layout will be added at the end of the base Instrument Config
            # Layout. There is also a method that could be overridden to add to the beginning,
            # Or you can override _get_ic_layout to completely change the layout.
            return (
                Div(
                    Div(
                        f'c_{config_instance}_ic_{instance}_readout_mode',
                        css_class='col'
                    ),
                    Div(
                        f'c_{config_instance}_ic_{instance}_defocus',
                        css_class='col'
                    ),
                    css_class='form-row'
                )
            )


    class SpectrographObservationForm(OCSFullObservationForm):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # Since you are adding fields to the acquisition mode, that is within the configuration
            for j in range(self.facility_settings.get_setting('max_configurations')):
                self.fields[f'c_{j+1}_acquisition_mode'] = forms.ChoiceField(
                    choices=self.mode_choices('acquisition', use_code_only=True), required=False, label='Acquisition Mode')
                self.fields[f'c_{j+1}_acquisition_exposure_time'] = forms.FloatField(
                    min_value=0.0,
                    help_text='Acquisition image exposure time',
                    label='Exposure Time', required=False
                )
                # This field leverages a helper method that gets a set of target choices from targets
                # in the same Target Group as your forms target.
                self.fields[f'c_{j+1}_acquisition_guide_star'] = forms.ChoiceField(
                    choices=(None, '') + self.target_group_choices(include_self=False),
                    required=False,
                    help_text='Set an acquisition guide star target. Must be in the same target group.',
                    label='Acquisition guide star target'
                )

        def get_instruments(self):
            # Here only the instruments that are of type SPECTRA are returned.
            instruments = super().get_instruments()
            return {code: instrument for (code, instrument) in instruments.items() if ('SPECTRA' == instrument['type'])}


        def configuration_type_choices(self):
            # Here only the configuration types that you want users to submit with are Returned.
            # By default, all "Schedulable" configuration types will be available, as defined in configdb.
            return [
                ('SPECTRUM', 'Spectrum'),
                ('REPEAT_SPECTRUM', 'Spectrum Sequence'),
                ('ARC', 'Arc'),
                ('LAMP_FLAT', 'Lamp Flat')
            ]

        def form_name(self):
            # This must be a unique identifier for the form.
            return 'spectrographs'

        def configuration_layout_class(self):
            # This method sets the Configuration Layout class. Here you are setting your
            # custom class defined above which adds your new acquisition fields to the form.
            return SpectrographConfigurationLayout

        def _build_acquisition_config(self, configuration_id):
            # This is called when submitting or validating the form, and it constructs the 
            # acquisition config payload. Here we will add our extra fields into the payload
            acquisition_config = super()._build_acquisition_config(configuration_id)
            if self.cleaned_data.get(f'c_{configuration_id}_acquisition_mode'):
                acquisition_config['mode'] = self.cleaned_data[f'c_{configuration_id}_acquisition_mode']
            if self.cleaned_data.get(f'c_{configuration_id}_acquisition_exposure_time'):
                acquisition_config['exposure_time'] = self.cleaned_data[f'c_{configuration_id}_acquisition_exposure_time']
            if self.cleaned_data.get(f'c_{configuration_id}_acquisition_guide_star'):
                target_details = self._build_target_fields(
                    self.cleaned_data[f'c_{configuration_id}_acquisition_guide_star'], 0
                )
                if 'extra_params' not in acquisition_config:
                    acquisition_config['extra_params'] = {}
                acquisition_config['extra_params']['guide_star'] = target_details            {

            return acquisition_config

The above code should define a form which only has spectrograph instruments, and adds three new
fields to the `acquisition_config` section of the form. 

Now that you have defined both new forms, your new OCS-based facility module should be complete!
Try reloading your TOM and navigating to the details page for a specific Target. You should see
your ``CustomOCS`` facility in the list, and clicking that should bring you to a page with the
observation forms you've just defined.

Observation Utility Methods
~~~~~~~~~~~~~~~~~~~~~~~~~~~

In the examples above, you modified the `_build_instrument_config()` and `_build_acquisition_config()`
methods to fill in those portions of the OCS request payload. The `OCSFullObservationForm`
has a number of utility methods that can be overridden to change specific parts of the observation submission form.
These can be reviewed
`here <https://github.com/TOMToolkit/tom_base/blob/dev/tom_observations/facilities/ocs.py#L826>`__.

Custom OCS Settings
~~~~~~~~~~~~~~~~~~~
For a more complicated OCS based facility implementation, you may want to override the base ``OCSSettings``
and create your own facility settings class. This is necessary to hook in facility site locations for
a visibility plot, and facility weather/availability information. To create your own custom settings
class, start by subclassing ``OCSSettings`` like this:

.. code-block:: python
 :linenos:

    # custom_ocs.py
    from tom_observations.facilities.ocs import OCSFacility, OCSSettings


    class CustomOCSSettings(OCSSettings):
        # Place default values for your settings here, if you don't require users to enter them in their settings.py
        default_settings = {
            'portal_url': 'my-custom-ocs-observation-portal-url',
            'archive_url': 'my-custom-ocs-archive-api-url',
            'api_key': '',
            'max_instrument_configs': 5,
            'max_configurations': 5
        }

        # This facility_name should be unique among your TOM facilities.
        # This is where the code will look for settings for this facility,
        # under FACILITIES -> facility_name in settings.py.
        def __init__(self, facility_name='CustomOCS'):
            super().__init__(facility_name=facility_name)

        def get_fits_facility_header_value(self):
            # Define what your custom facilities fits header value is in your data products
            return 'MyFacility'

        def get_sites(self):
            # Return a dictionary of site names to site details here, used for visibility calculations.
            return {
                'My Site 1': {
                    'sitecode': 'ms1',
                    'latitude': -31.272,
                    'longitude': 149.07,
                    'elevation': 1116
                },
                'My Site 2': {
                    'sitecode': 'ms2',
                    'latitude': -32.38,
                    'longitude': 20.81,
                    'elevation': 1804
                },
            }
        
        def get_weather_urls(self):
            # Returns a dictionary of sites with weather urls for retrieving weather data for each site
            return {
                'code': self.facility_name,
                'sites': [
                    {
                        'code': site['sitecode'],
                        'weather_url': f'https://my-weather-url-base/?site={site["sitecode"]}'
                    }
                    for site in self.get_sites().values()]
            }

    class CustomOCSFacility(OCSFacility):
        name = 'CustomOCS'
        observation_forms = {
            'Instrument1': Instrument1ObservationForm,
            'Spectra': SpectraObservationForm    
        }

        def __init__(self, facility_settings=CustomOCSSettings('CustomOCS')):
            super().__init__(facility_settings=facility_settings)

Notice that the only change to the ``CustomOCSFacility`` was the overriding of the `__init__()`
method to set the `facility_settings` class to be an instance of our newly created ``CustomOCSSettings``
class. Please review
`the base OCSSettings class <https://github.com/TOMToolkit/tom_base/blob/dev/tom_observations/facilities/ocs.py#L23>`__
to see what other behaviour can be customized, including certain fields `help_text` or certain archive
data configuration information.
