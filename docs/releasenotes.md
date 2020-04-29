### 1.5.0

- Introduced a manual facility interface for classical observing.
- Introduced a view and corresponding form to add existing API-based observations to a Target.
- Introduced a view and corresponding form to update an existing manual observation with an API-based observation ID.


#### What to watch out for

- For facility implementers: in order to support a Manual Facility Interface, the team created a `BaseObservationFacility` and two abstract implementations of it, `BaseRoboticObservationFacility` and `BaseManualObservationFacility`. `BaseRoboticObservationFacility` was aliased as `GenericObservationFacility` to support backwards compatibility, but will be removed in 2.0.