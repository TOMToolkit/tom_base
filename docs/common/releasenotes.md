# Release Notes

### 1.6.1

- This release pins the Django version in order to address a security vulnerability.

#### What to watch out for

- The Django version is now pinned at 3.0.7, where previously it allowed >=2.2. You'll need to ensure that any custom code is compatible with Django >=3.0.7.

### 1.6.0

- New methods expand the Facility API to support reporting Facility status and weather: `get_facility_status()` and `get_facility_weather_url()`. When these methods are implemented by a Facility provider, this information can be made available in your TOM.
- A new template tag, `facility_status()`, is available to present this information.

### 1.5.0

- Introduced a manual facility interface for classical observing.
- Introduced a view and corresponding form to add existing API-based observations to a Target.
- Introduced a view and corresponding form to update an existing manual observation with an API-based observation ID.


#### What to watch out for

- For facility implementers: in order to support a Manual Facility Interface, the team created a `BaseObservationFacility` and two abstract implementations of it, `BaseRoboticObservationFacility` and `BaseManualObservationFacility`. `BaseRoboticObservationFacility` was aliased as `GenericObservationFacility` to support backwards compatibility, but will be removed in 2.0.