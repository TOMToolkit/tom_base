Publish and Subscribe to a Kafka Stream
---------------------------------------

Publishing data to a stream and subscribing to a stream are handled independently and we describe each below.

.. note::

   For TOMToolkit version 3, all HERMES-specific code has moved from ``tom_base`` into the
   ``tom_hermes`` package and the old import paths in ``tom_base`` are removed. If you are upgrading from a
   pre-refactor ``tom_base`` / ``tom_hermes``, see the *Migration summary* at the bottom of this page for the
   list of dotted paths that need to be updated.


SharingBackend integration point
################################

Data-sharing destinations are discovered by plug-in rather than by hardcoded string match. An app advertises
its SharingBackend classes by adding a ``sharing_backends()`` method (i.e. integration point) to its AppConfig;
``tom_common.sharing`` iterates installed apps, imports the listed class paths, and builds a registry keyed by
each backend's ``name``. Existing backends:

* **``TomToolkitSharingBackend``** (``tom_common.sharing``) — "share with another TOM Toolkit-based TOM."
  Registered by ``tom_common.apps.TomCommonConfig``. ``name = 'tom'``.
* **``HermesSharingBackend``** (``tom_hermes.sharing``) — "publish to HERMES." Registered by
  ``tom_hermes.apps.TomHermesConfig``. ``name = 'hermes'``.

The share-destination form field's value is formatted as ``'<name>:<sub-destination>'`` (for example
``'hermes:hermes.test'`` or ``'tom:tom_b'``); ``DataShareView.post`` parses the prefix and dispatches to the
matching backend's ``share()`` method. A future publisher is registered by writing a ``SharingBackend``
subclass in its app and returning it from that app's AppConfig ``sharing_backends()`` hook — no changes to
``tom_base`` required.

To write a new SharingBackend, subclass ``tom_common.sharing.SharingBackend`` and implement ``share()`` and
``get_destination_choices()``. See the ``tom_common.sharing.SharingBackend`` docstring and the two included
subclasses for reference.


Publish Data to a Kafka Topic
#############################

TOM Toolkit supports publishing data to a Kafka stream such as `Hermes <https://hermes.lco.global>`_ (an interface to
`HOPSKOTCH <https://hop.scimma.org>`_) and `GCNClassicOverKafka <https://gcn.nasa.gov>`_.

When sharing photometry data via Hermes, the TOM publishes the data to be shared to a topic on the HOPSKOTCH
Kafka stream. To submit via the Hermes API, you will need a HERMES API Key. You can store it either per-user
on the ``HermesProfile`` (see *Per-user HERMES credentials* below) or TOM-wide in ``settings.DATA_SHARING``.
``HermesProfile`` credentials take precedence when set.

To customize what data is sent to HERMES from your ReducedDatum or Target models, subclass
``tom_hermes.sharing.HermesDataConverter`` and override the ``get_hermes_*`` methods to pull the data out of
your TOM's model fields. Provide the class dotpath in ``settings.DATA_SHARING['hermes']['DATA_CONVERTER_CLASS']``.
For more information on the structure HERMES expects, see the
`API Schema Registry here <https://hermes.lco.global/about>`_.


Configuring your TOM to publish data
************************************

``settings.DATA_SHARING`` is a dict keyed by destination name. Multiple TOM-to-TOM destinations are supported
(add one entry per destination TOM); the HERMES destination is identified by the presence of
``HERMES_API_KEY``.

Authentication for TOM-to-TOM destinations: prefer a DRF API key via the ``API_KEY`` key (TOM Toolkit
auto-generates a DRF token per user, and a service-account token can be created on the destination TOM);
fall back to HTTP Basic via ``USERNAME`` and ``PASSWORD``.

.. code:: python

    DATA_SHARING = {
        # One or more TOM-to-TOM destinations. This configuration is used by
        # tom_common.sharing.TomToolkitSharingBackend.
        'tom_alice': {
            'DISPLAY_NAME': 'TOM Alice',
            'BASE_URL':     'https://tom-alice.example.org/',
            'API_KEY':      os.getenv('TOM_ALICE_API_KEY', ''),   # preferred; Token auth
        },
        'tom_bob': {
            'DISPLAY_NAME': 'TOM Bob',
            'BASE_URL':     'https://tom-bob.example.org/',
            'USERNAME':     os.getenv('TOM_BOB_USERNAME', ''),  # fallback: HTTP Basic; not preferred
            'PASSWORD':     os.getenv('TOM_BOB_PASSWORD', ''),
        },

        # HERMES destination. This configuration used by tom_hermes.sharing.HermesSharingBackend.
        'hermes': {
            'DISPLAY_NAME':         os.getenv('HERMES_DISPLAY_NAME', 'Hermes'),
            'BASE_URL':             os.getenv('HERMES_BASE_URL', 'https://hermes.lco.global/'),
            'HERMES_API_KEY':       os.getenv('HERMES_API_KEY', ''),
            'DEFAULT_AUTHORS':      os.getenv('HERMES_DEFAULT_AUTHORS', ''),
            'USER_TOPICS':          ['hermes.test', 'tomtoolkit.test'],
            'DATA_CONVERTER_CLASS': 'tom_hermes.sharing.HermesDataConverter',
        },
    }


Per-user HERMES credentials
***************************

Instead of (or in addition to) a TOM-wide HERMES API key in ``settings.DATA_SHARING``, each TOM user can
store their own HERMES credentials on the user profile page. Visit the profile page and click the pencil
icon on the "HERMES Credentials" card to set:

* ``HERMES API Key`` — the user's HERMES submit API key.
* ``Hopskotch Username`` / ``Hopskotch Password`` — SCRAM credentials for reading from Hopskotch.

Lookup order when publishing: the user's ``HermesProfile`` first; if unset, the TOM-wide
``settings.DATA_SHARING['hermes']`` fallback.


Subscribe to a Kafka Topic
##########################

TOM Toolkit allows a TOM to subscribe to a topic on a Kafka stream, ingesting messages from that topic and handling the data.
This could involve simply logging the message or extracting the data from the message and saving it if it is properly formatted.


Configuring your TOM to subscribe to a stream
**********************************************

First add ``tom_alertstreams`` (and ``tom_hermes``, if you plan to subscribe to HERMES topics) to your
``INSTALLED_APPS``:

.. code:: python

    INSTALLED_APPS = [
        ...
        'tom_alertstreams',
        'tom_hermes',
    ]

Then add an ``ALERT_STREAMS`` configuration dictionary. This gives the credentials for the various streams
and maps each subscribed topic to the dotted path of its handler callable.

A HERMES alert handler lives at ``tom_hermes.alertstreams.ingester.hermes_alert_handler``. If you are
upgrading from a pre-refactor TOM, update any ``TOPIC_HANDLERS`` dotted paths that pointed at the old
location (``tom_dataproducts.alertstreams.hermes_ingester.hermes_alert_handler``) — the old path no longer
exists.

.. code:: python

    ALERT_STREAMS = [
        {
            'ACTIVE': True,
            'NAME': 'tom_alertstreams.alertstreams.hopskotch.HopskotchAlertStream',
            'OPTIONS': {
                'URL': 'kafka://kafka.scimma.org/',
                'USERNAME': os.getenv('SCIMMA_CREDENTIAL_USERNAME', ''),
                'PASSWORD': os.getenv('SCIMMA_CREDENTIAL_PASSWORD', ''),
                'TOPIC_HANDLERS': {
                    'tomtoolkit.test': 'tom_hermes.alertstreams.ingester.hermes_alert_handler',
                },
            },
        },
    ]


HERMES as a query source (DataService)
######################################

``tom_hermes`` also registers a ``DataService`` subclass — ``tom_hermes.dataservices.hermes.HermesDataService`` —
so users can query HERMES from the Data Services nav-bar entry. The DataService queries the LCO-maintained
``/api/v0/query`` wrapper, which proxies to the SCIMMA archive. Selecting rows from the query results and
clicking "Create Targets" runs through the same ``ingest_hermes_alert`` function that the live Hopskotch
stream handler calls. So, archive-ingest (DataService) and stream-ingest (alertstreams) produce identical
TOM database entries for the same message.


Migration summary
#################

For TOMToolkit v3, all HERMES interfaces have been refactor from ``tom_base`` to ``tom_hermes``.
When upgrading from TOMToolkit v2, the following paths must be updated:
j
* ``ALERT_STREAMS`` ``TOPIC_HANDLERS`` dotted paths:
  ``tom_dataproducts.alertstreams.hermes_ingester.hermes_alert_handler`` →
  ``tom_hermes.alertstreams.ingester.hermes_alert_handler``.
* ``DATA_SHARING['hermes']['DATA_CONVERTER_CLASS']`` dotted path:
  ``tom_dataproducts.alertstreams.hermes_publisher.HermesDataConverter`` →
  ``tom_hermes.sharing.HermesDataConverter``.
* Direct imports: any code importing ``publish_to_hermes``, ``preload_to_hermes``,
  ``BuildHermesMessage``, ``HermesDataConverter``, ``HermesMessageException``,
  ``create_hermes_alert``, ``get_hermes_data_converter_class``, or ``get_hermes_topics``
  from ``tom_dataproducts.alertstreams.hermes_publisher`` must now import from
  ``tom_hermes.sharing``.
* Direct imports: any code importing ``hermes_alert_handler``, ``ingest_hermes_alert``,
  ``get_hermes_phot_value``, ``create_new_hermes_target``,
  ``get_or_create_uuid_from_metadata``, or ``HERMES_SPECTROSCOPY_FILE_EXTENSIONS``
  from ``tom_dataproducts.alertstreams.hermes_ingester`` must now import from
  ``tom_hermes.alertstreams.ingester``.
* The ``share_data_with_hermes`` / ``share_target_list_with_hermes`` / ``share_data_with_tom``
  functions in ``tom_dataproducts.sharing`` are removed. Replace call sites with
  ``tom_common.sharing.get_sharing_backend(name)().share(...)``.
