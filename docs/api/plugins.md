Plugins
---

### TOM Toolkit Plugins

Additional functionality can be added to the TOM Toolkit in the form of plugins.
These may range from adding the ability to interface with additional
observatories, to providing additional plotting or data analytics functionality.

### tom-alerts-dash

This module supplements the tom_alerts module with Plotly Dash support for more responsive broker views.

[Github](https://github.com/TOMToolkit/tom_alerts_dash)

[Installation Instructions](https://github.com/TOMToolkit/tom_alerts_dash#installation)

### tom-antares
This module provides the ability to query and/or listen to Antares alert streams
from within a TOM.

[Github](https://github.com/TOMToolkit/tom_antares)

[Installation Instructions](https://github.com/TOMToolkit/tom_antares)

#### Compatibility Notes

If you're on Mac OS, it should be noted that the Antares client library has a dependency
that only supports Mac OS 10.13 or later. If you try to run `./manage.py migrate` on an
earlier version, you may see an error.

### tom-nonsidereal-airmass

This module provides a templatetag supporting visibility plots for non-sidereal targets. This plugin is fully
supported by the TOM Toolkit team; however, non-sidereal visibility calculations require the PyEphem library, which is
minimally supported while its successor is in development. The library used for the TOM Toolkit sidereal visibility,
`astroplan`, does not yet support non-sidereal visibility calculations.

[Github](https://github.com/TOMToolkit/tom_nonsidereal_airmass)

[Installation Instructions](https://github.com/TOMToolkit/tom_nonsidereal_airmass)

### tom-lt

This module provides the ability to submit observations to the Liverpool Telescope Phase 2 system. It is in a very
alpha state, with little error handling and minimal instrument options, but can successfully submit well-formed
observation requests.

[Github](https://github.com/TOMToolkit/tom_lt)

[Installation Instructions](https://github.com/TOMToolkit/tom_lt/blob/main/README.md#installation-and-setup)

### tom-registration

This module provides two registration flows for users to self-register--either requiring approval, or not.

[Github](https://github.com/TOMToolkit/tom_registration)

[Installation Instructions](https://github.com/TOMToolkit/tom_registration#installation)

### tom-hermes

This module provides an interface to query the [Hermes alert broker](https://hermes.lco.global).

[Github](https://github.com/TOMToolkit/tom_hermes)

[Installation Instructions](https://github.com/TOMToolkit/tom_hermes#installation)
