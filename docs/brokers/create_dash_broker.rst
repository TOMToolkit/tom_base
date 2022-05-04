Plotly Dash Broker Modules in the TOM Toolkit
#############################################

An optional plugin module for the TOM Toolkit is the `tom_alerts_dash <https://github.com/TOMToolkit/tom_alerts_dash>`_ module.
``tom_alerts_dash`` is built using `Plotly Dash <https://dash.plotly.com/>`_, a library that provides a Python wrapper for 
ReactJS, allowing you to generate ReactJS code by writing Python. The inclusion of Plotly Dash in the TOM Toolkit allows for
responsive, single-page-app-styled views that don't require hard page reloads for simple actions.

The instructions for installing ``tom_alerts_dash`` into your TOM are in the repository itself. However, this guide provides 
instructions on writing your own broker module that can be used with the responsive views.

The primary Dash object that we'll be using is that of a `DataTable <https://dash.plotly.com/datatable>`_, which is the 
component that ``tom_alerts_dash`` uses to display the Dash broker data. It's recommended to consult the 
`Reference <https://dash.plotly.com/datatable/reference>`_ when implementing a Dash broker module, as the properties for 
columns and inputs are described there.

Creating a Dash Broker Module
*****************************

Within ``tom_alerts_dash``, a broker module can be created with a custom table and custom inputs. That means that while MARS 
may provide filters for real-bogus score, ALeRCE can instead provide filters for early and late classifier. Additionally, 
the set of columns MARS displays can be completely different than ALeRCE. For a custom broker module, that means that 
an implementer is not limited to a small set of available filters.

Prerequisite
============

The first thing to keep in mind when beginning this process is that a Dash broker module can only be created for an existing 
TOM Toolkit broker module. At the moment, the TOM Toolkit provides modules for the following brokers:

  * ALeRCE
  * ANTARES (via a plugin module)
  * Gaia
  * Lasair
  * MARS
  * SCIMMA Skip (via a plugin module)
  * Scout
  * Transient Name Server

The TOM Toolkit provides Dash modules for the following brokers:

  * ALeRCE
  * MARS
  * SCIMMA Skip

Required Dash Broker Class Methods
==================================

For the following instructions, we'll be using the ``tom_alerts_dash`` ``MARSDashBroker`` module as an example. The code can 
be found `here <https://github.com/TOMToolkit/tom_alerts_dash/blob/main/tom_alerts_dash/brokers/mars.py>`_.

A ``tom_alerts_dash`` broker module is required to inherit from two classes: the TOM Toolkit broker module that it represents, 
and the ``tom_alerts_dash`` ``GenericDashBroker`` interface.

.. code-block:: python

    from tom_alerts.brokers.mars import MARSBroker, MARSQueryForm, MARS_URL
    from tom_alerts_dash.alerts import GenericDashBroker


    class MARSDashBroker(MARSBroker, GenericDashBroker):

``get_dash_columns`` method
---------------------------

The ``get_dash_columns`` method will control which columns are visible in the Dash Datatable for a custom broker module. The 
return value must be a list of dictionaries, with each having, at minimum, an ``id``, ``name``, and ``type``. If a column is 
to appear as a link, the dictionary must also contain the key/value pair ``'presentation': 'markdown'``.

The ``id`` will need to correspond with the key in the eventual data dictionary, so take note of that.

.. code-block:: python


    class MARSDashBroker(MARSBroker, GenericDashBroker):

        ...

        def get_dash_columns(self):
            return [
                {'id': 'objectId', 'name': 'Name', 'type': 'text', 'presentation': 'markdown'},
                {'id': 'ra', 'name': 'Right Ascension', 'type': 'text'},
                {'id': 'dec', 'name': 'Declination', 'type': 'text'},
                {'id': 'magpsf', 'name': 'Magnitude', 'type': 'text'},
                {'id': 'rb', 'name': 'Real-Bogus Score', 'type': 'text'},
            ]


``get_dash_filters`` method
---------------------------

The ``get_dash_filters`` method defines the presentation of the filters that are available to the end user. The layout is 
defined using the ``dash_bootstrap_components`` and ``dash_html_components`` modules, while the inputs are provided by 
the ``dash_core_components`` method. It's important to take note of the ``id`` property on each ``dcc.Input`` element, 
as they will be needed for the ``get_callback_inputs`` method.

.. important::
    Your input ids MUST be unique, or they may conflict with other broker inputs! It's recommended that your ids be 
    prefixed with the name of your broker, i.e. mars-objname-search.

.. code-block:: python

    import dash_bootstrap_components as dbc
    import dash_html_components as dhc
    import dash_core_components as dcc


    class MARSDashBroker(MARSBroker, GenericDashBroker):

        ...

        def get_dash_filters(self):
            filters = dhc.Div([
                dbc.Row([
                    dbc.Col(dcc.Input(
                        id='mars-objname-search',
                        type='text',
                        placeholder='Object Name Search',
                        debounce=True
                    ), width=3),
                    dbc.Col(dcc.Input(
                        id='mars-magpsf-min',
                        type='number',
                        placeholder='Magnitude Minimum',
                        debounce=True
                    ), width=3),
                    dbc.Col(dcc.Input(
                        id='mars-rb-min',
                        type='number',
                        placeholder='Real-Bogus Minimum',
                        debounce=True
                    ), width=3)
                ], style={'padding-bottom': '10px'}, justify='start'),
                dbc.Row([
                    dbc.Col(dcc.Input(
                        id='mars-cone-ra',
                        type='text',
                        placeholder='Right Ascension',
                        debounce=True
                    ), width=3),
                    dbc.Col(dcc.Input(
                        id='mars-cone-dec',
                        type='text',
                        placeholder='Declination',
                        debounce=True
                    ), width=3),
                    dbc.Col(dcc.Input(
                        id='mars-cone-radius',
                        type='text',
                        placeholder='Radius',
                        debounce=True
                    ), width=3)
                ], style={'padding-bottom': '10px'}, justify='start')
            ])
            return filters

``get_callback_inputs`` method
------------------------------

The ``get_callback_inputs`` method defines the triggers for the callback filter function that an implementer will eventually 
define. Essentially, for each input object, when the specified property changes, it will trigger the callback.

In the MARS example below, the triggers are pretty straightforward. Each ``dcc.Input`` object has a ``value`` property that 
is used as the trigger. It is unlikely that an implementer will use a filter that differs from this, but one should be sure 
to consult the Dash documentation to ensure that this is the case.

It is important to note that the ``dcc.Input`` objects in ``get_dash_filters`` are different than the ``Input`` objects in 
the below example, which is imported from ``dash.dependencies``.

One further note is that brokers implementing pagination, as they all should do, will need to call the superclass 
implementation of ``get_callback_inputs``, which provides the two inputs for ``page_number`` and ``page_size``, although 
``page_size`` is not currently used in any form.

.. code-block:: python

    from dash.dependencies import Input


    class MARSDashBroker(MARSBroker, GenericDashBroker):

        ...

        def get_callback_inputs(self):
            inputs = super().get_callback_inputs()
            inputs += [
                Input('mars-objname-search', 'value'),
                Input('mars-cone-ra', 'value'),
                Input('mars-cone-dec', 'value'),
                Input('mars-cone-radius', 'value'),
                Input('mars-magpsf-min', 'value'),
                Input('mars-rb-min', 'value'),
            ]
            return inputs

``callback`` method
-------------------

A ReactJS/Plotly Dash concept that is important to know for this method is that of the callback. A callback is a function that 
runs asynchronously after being triggered, which is what enables a responsive page that doesn't require hard reloads.

Each ``tom_alerts_dash`` module is required to implement a callback. The callback function will trigger on a change to 
any of the previously defined inputs. The callback function will accept the input values and query the broker to return 
a set of alerts to the user, which should be a list of dictionaries.

An important note is that the method signature requires a parameter for each input defined in ``get_callback_inputs``, and the 
order matters. It's also important to remember that if pagination was enabled by calling the superclass implementation in 
``get_callback_inputs``, ``page_current`` and ``page_size`` must be the first two arguments after ``self``.

Each dictionary returned by ``callback`` must have all of the values that are to be displayed at the top level of the 
dictionary. The keys of the dictionary must correspond to the ``id`` values of each column specified in ``get_dash_columns``. 
Because most brokers likely return a multi-level dictionary, the default TOM Toolkit Dash broker modules all implement a method 
``flatten_dash_alerts`` to transform the alerts list into a Dash Datatable-compatible format. Though it is not required 
to implement this method in a custom broker, it's recommended in order to maintain clean and readable code.

In the below example, a ``PreventUpdate`` exception is raised in the case that not all cone search values are populated. This 
exception simply prevents the callback from firing due to the incomplete data, but does not propogate an error to the end user.

.. code-block:: python

    from dash.exceptions import PreventUpdate

    from tom_alerts.brokers.mars import MARSBroker, MARSQueryForm


    class MARSDashBroker(MARSBroker, GenericDashBroker):

        def callback(self, page_current, page_size, objectId, cone_ra, cone_dec, cone_radius, magpsf__gte, rb__gte):
            logger.info('Entering MARS callback...')
            cone_search = ''
            if any([cone_ra, cone_dec, cone_radius]):
                if all([cone_ra, cone_dec, cone_radius]):
                    cone_search = ','.join([cone_ra, cone_dec, cone_radius])
                else:
                    raise PreventUpdate

            form = MARSQueryForm({
                'query_name': 'dash query',
                'broker': self.name,
                'objectId': objectId,
                'magpsf__gte': magpsf__gte,
                'rb__gte': rb__gte,
                'cone': cone_search
            })
            form.is_valid()

            parameters = form.cleaned_data
            parameters['page'] = page_current + 1  # Dash pagination is 0-indexed, but MARS is 1-indexed

            alerts = self._request_alerts(parameters)['results']
            return self.flatten_dash_alerts(alerts)

``flatten_dash_alerts`` method
------------------------------

As stated above, the ``flatten_dash_alerts`` method is not required for a custom implementation of a ``tom_alerts_dash`` broker 
module, but exists for convenience. The below example creates a new dictionary for each alert that is one level deep, save for 
original alert. Each key in the dictionary corresponds to a column defined in ``get_dash_columns``, for example:

.. code-block:: python

    {'id': 'objectId', 'name': 'Name', 'type': 'text', 'presentation': 'markdown'}

    url = f'{MARS_URL}/{alert["lco_id"]}/'
    flattened_alerts.append({
        'objectId': f'[{alert["objectId"]}]({url})',
    ...

The MARS example also does some further data transformation. The objectId value is rendered as a markdown link, enabling an 
embedded link in the DataTable. The example also uses a couple of TOM Toolkit utility methods to convert RA/Declination to 
sexagesimal and to truncate decimals to 4 places.

It should be noted that in this example, and in all built-in Dash broker modules, ``flatten_dash_alerts`` includes the
original alert with the key ``alert``. This is critical in order to enable creation of targets from alerts.

.. code-block:: python

    from tom_alerts.brokers.mars import MARSBroker, MARSQueryForm, MARS_URL
    from tom_common.templatetags.tom_common_extras import truncate_number
    from tom_targets.templatetags.targets_extras import deg_to_sexigesimal


    class MARSDashBroker(MARSBroker, GenericDashBroker):

        def flatten_dash_alerts(self, alerts):
            flattened_alerts = []
            for alert in alerts:
                url = f'{MARS_URL}/{alert["lco_id"]}/'
                flattened_alerts.append({
                    'objectId': f'[{alert["objectId"]}]({url})',
                    'ra': deg_to_sexigesimal(alert['candidate']['ra'], 'hms'),
                    'dec': deg_to_sexigesimal(alert['candidate']['dec'], 'dms'),
                    'magpsf': truncate_number(alert['candidate']['magpsf']),
                    'rb': truncate_number(alert['candidate']['rb']),
                    'alert': alert
                })
            return flattened_alerts

``validate_filters`` method
---------------------------

The ``validate_filters`` method provides a way to propogate error messages from input validation up to the user. It is 
wired as a callback to a front-end component that creates alert boxes, but can also be called from a broker's 
``callback`` method in order to do validation prior to attempting a query.

In addition to all of the input parameters for ``callback()``, this method accepts a ``list`` of ``dbc.Alert`` objects 
that are currently rendered, so that they can be appended to and will not be inadvertently overwritten for the end user.

.. code-block:: python

    import dash_bootstrap_components

    from tom_alerts.brokers.mars import MARSQueryForm


    class MARSDashBroker(MARSBroker, GenericDashBroker):

        def validate_filters(self, page_current, page_size, objectId, cone_ra, cone_dec, cone_radius, magpsf_lte, rb_gte,
                         errors_state):
        errors = []

        cone_search = ''
        if any([cone_ra, cone_dec, cone_radius]):
            if all([cone_ra, cone_dec, cone_radius]):
                cone_search = ','.join([cone_ra, cone_dec, cone_radius])
            else:
                errors.append('All of RA, Dec, and Radius are required for a cone search.')

        form = MARSQueryForm({
            'query_name': 'dash query',
            'broker': self.name,
            'objectId': objectId,
            'magpsf__lte': magpsf_lte,
            'rb__gte': rb_gte,
            'cone': cone_search
        })
        form.is_valid()

        for field, field_errors in form.errors.items():
            for field_error in field_errors.get_json_data():
                errors.append(f'{field}: {field_error["message"]}')

        for error in errors:
            errors_state.append(dbc.Alert(error, dismissable=True, is_open=True, duration=5000, color='warning'))

        return errors_state

Add custom Dash broker module to ``settings.py``
================================================

To get a custom Dash broker module to show up in a TOM, it must be added to ``settings.py`` ``TOM_ALERT_DASH_CLASSES``.

.. code-block:: python

    TOM_ALERT_DASH_CLASSES = [
        'tom_alerts_dash.brokers.alerce.ALeRCEDashBroker',
        'tom_alerts_dash.brokers.mars.MARSDashBroker',
        'tom_alerts_dash.brokers.scimma.SCIMMADashBroker',
    ]

Summary
*******

Though there's a learning curve to Dash, the implementation of ``tom_alerts_dash`` is intended to provide a relatively convenient 
and quick way to create a responsive table for displaying alerts from a preferred broker. As the Dash library evolves, the 
TOM Toolkit will continue to build on the provided features. For implementers, the following tips are important to keep in 
mind to make the process as smooth as possible:

  * Implement the four (plus one optional) methods that are required to render a new broker
      * ``callback()``
      * ``get_callback_inputs()``
      * ``get_dash_filters()``
      * ``get_dash_columns()``
      * ``flatten_dash_alerts()`` (optional)
  * Reference the Dash documentation
  * Watch the "Console" tab of developer tools (control+shift+i in Chrome, control+shift+k in Firefox) to see any ReactJS errors during implementation
    
