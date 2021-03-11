# Release Notes

## 2.5.3

- Retains the selected tab on reload for target detail page, as well as selected filters on target list and observation list when updating statuses.
- Adds new statuses supported by the LCO facility.

### What to watch out for

- In order to leverage the tab retention, you'll need to copy the changes in ``tom_targets/target_detail.html``, ``tom_observations/observation_list``, and ``tom_targets/target_list.html``. You can review [this pull request](https://github.com/TOMToolkit/tom_base/pull/436/files) to see what has changed.

## 2.5.2

- Fixes the erroneous use of ``photon_flux`` and replaces it with ``flux`` for spectroscopic data processing. It also fixes past usage of ``photon_flux`` using a migration script.

### What to watch out for

- This release requires running ``./manage.py migrate``.
- This release will modify all ``ReducedDatum`` objects with a ``data_type`` of ``'spectroscopy'``. It is highly recommended that you back up your data prior to running the migration script.

## 2.5.1

- Fixes the ObservationRecordCancelView and adds a path to it to urls.py. It is now accessible via tom_observations:cancel.

## 2.5.0

- Added API endpoints for submit, list, and detail for ``ObservationRecord``s.

## 2.4.2

- Fixes a bug when submitting observations for dynamic cadences produced by the photometric sequence form.
- Fixes a bug showing an inappropriate error message when LCO validation fails.

## 2.4.1

Release 2.4.1 was yanked and should not be installed.

## 2.4.0

- Updated TNS URL to the new URL used by TNS in the broker and harvester modules.
- Modified ``ObservationRecord``, ``ObservationTemplate``, ``BrokerQuery``, and ``ReducedDatum`` to use ``JSONField`` instead of ``TextField``.
- Dependency updates.

### What to watch out for

- This release requires running ``./manage.py migrate``.
- Any uses of ``ObservationRecord.serialize_parameters()``, ``ObservationRecord.parameters_as_dict``, ``BrokerQuery.parameters_as_dict``, ``ObservationTemplate.serialize_parameters()`` should be replaced with ``<ModelName>.parameters``.

## 2.3.0

- Added a new observing form for MUSCAT submissions to LCO.
- Fixed a bug resulting in observations with unknown status not showing up in alert bubble on target detail page.

### What to watch out for

- If you have customized your ``target_detail.html``, the line ``{% target_unknown_statuses object %}`` was moved to be outside of the ``{% if %}`` block, and will need to be updated to correct the bug.

## 2.2.0

- Added a new ``TargetNameSearchView`` that allows a user to search for a target name and be redirected to the target detail page for that name, provided there's only one result.

## 2.1.1

- Fixed a bug that allowed negative exposure time and exposure count in the LCOPhotometricSequenceForm.
- Fixed out-of-date references to LCOObservationForm in documentation.
- Added links and descriptions of new supported modules to documentation.

## 2.1.0

- Updated MARS and ALeRCE modules to support Dash Broker changes.
- Various documentation improvements.

## 2.0.1

- Fixed a bug in SimbadHarvester due to changes in the Simbad API.
- Added a Simbad canary test.

## 2.0.0

- Renamed `ALERT_CREDENTIALS` and `BROKER_CREDENTIALS` to `BROKERS` as a catchall for any broker-specific values.
- Added support for custom `CadenceStrategy` layouts.
- Moved settings for `TNSHarvester` into `settings.HARVESTERS` to maintain consistency.
- Updated `tom_alerts.GenericBroker` interface to support submission upstream to a broker, if implemented.
- Fixed `TNSBroker` to get the correct object name.
- Added stub `SCIMMABroker`.
- Removed `tom_publications` from `tom_base`, and placed it in a separate `tom_publications` repository.
- Upgraded a number of dependencies, including `astroplan`, `astropy`, and multiple `django`-related libraries.
- Added tests for `lco.py`, `soar.py`, `alerce.py`, and `mars.py`.
- Added canary tests for `mars.py` and `alerce.py`.

### Breaking changes

- Migrations are required for this version.
- Due to the renaming of `BROKER_CREDENTIALS` and `ALERT_CREDENTIALS` to `BROKERS`, TOM Toolkit users will need to consolidate their broker configurations in `settings.py` into the `BROKERS` dict.
- Because the built-in cadence strategies were moved into their own files, users of the cadence strategies will need to update their `settings.TOM_CADENCE_STRATEGIES` to include the values as seen in this commit: https://github.com/TOMToolkit/tom_base/blob/82101a92a9c19f0ff8ab0f59ecb758bc47824252/tom_base/settings.py#L214
- Users of the `TNSHarvester` will need to introduce a dict in `settings` called `HARVESTERS` with a sub-dict `TNS` to store the relevant `api_key`.
- Due to the removal of `tom_publications`, TOM Toolkit users will need to either add `tom_publications` to their dependencies, or:
  - Remove `tom_publications` from `INSTALLED_APPS`.
  - Remove `publications_extras` from the following templates, if they've been customized: `observation_groups.html`, `target_grouping.html`.
  - Remove references to `latex_button_group` from the templates referenced above, if they've been customized.
- The `LCOBaseForm` methods `instrument_choices`, `instrument_to_type`, and `filter_choices` were re-implemented as static methods, and any subclasses will need to add a `staticmethod` decorator, modify the method signature, and replace calls to `self` within the method to calls to the class name.

## 1.6.1

  - This release pins the Django version in order to address a security vulnerability.

### What to watch out for

  - The Django version is now pinned at 3.0.7, where previously it allowed >=2.2. You'll need to ensure that any custom code is compatible with Django >=3.0.7.

## 1.6.0

  - New methods expand the Facility API to support reporting Facility status and weather: `get_facility_status()` and `get_facility_weather_url()`. When these methods are implemented by a Facility provider, this information can be made available in your TOM.
  - A new template tag, `facility_status()`, is available to present this information.

## 1.5.0

  - Introduced a manual facility interface for classical observing.
  - Introduced a view and corresponding form to add existing API-based observations to a Target.
  - Introduced a view and corresponding form to update an existing manual observation with an API-based observation ID.


### What to watch out for

  - For facility implementers: in order to support a Manual Facility Interface, the team created a `BaseObservationFacility` and two abstract implementations of it, `BaseRoboticObservationFacility` and `BaseManualObservationFacility`. `BaseRoboticObservationFacility` was aliased as `GenericObservationFacility` to support backwards compatibility, but will be removed in 2.0.
