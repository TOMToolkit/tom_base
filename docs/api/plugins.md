Plugins
---

### TOM Toolkit Plugins

Additional functionality can be added to the TOM Toolkit in the form of plugins.
These may range from adding the ability to interface with additional
observatories, to providing additional plotting or data analytics functionality.

### tom-antares
This module provides the ability to query and/or listen to Antares alert streams
from within a TOM.

[Github](https://github.com/TOMToolkit/tom_antares)

[Installation Instructions](https://github.com/TOMToolkit/tom_antares)

#### Compatibility Notes

If you're on Mac OS, it should be noted that the Antares client library has a dependency
that only supports Mac OS 10.13 or later. If you try to run `./manage.py migrate` on an
earlier version, you may see an error.
