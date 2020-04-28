### 1.5.0

- Introduced a manual facility interface for classical observing.


#### What to watch out for

- For facility implementers: in order to support a Manual Facility Interface, the team created a `BaseObservationFacility` and two abstract implementations of it, `BaseRoboticObservationFacility` and `BaseManualObservationFacility`. `BaseRoboticObservationFacility` was aliased as `GenericObservationFacility` to support backwards compatibility, but will be removed in 2.0.