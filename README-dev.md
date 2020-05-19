# TOM Toolkit
[![Build Status](https://travis-ci.org/TOMToolkit/tom_base.svg?branch=master)](https://travis-ci.org/TOMToolkit/tom_base)
[Documentation](https://tom-toolkit.readthedocs.io/en/latest/)

![logo](tom_common/static/tom_common/img/logo-color.png)

This README-dev is intended for maintainers of the repository for information on releases, standards, and anything that 
isn't pertinent to the wider community.

## Deployment
The [PyPi](https://pypi.org/project/tomtoolkit/) package is kept under the Las Cumbres Observatory PyPi account. The 
development and master branches are deployed automatically by TravisCI upon tagging either branch.

In order to trigger a PyPi deployment of either development or master, the branch must be given an annotated tag that 
matches the correct version format. The version formats are as follows:
 
|             | Development  | Master       | All other branches |
|-------------|--------------|--------------|--------------------|
| Tagged      | Push to PyPi | Push to PyPi | No effect          |
| Not tagged  | No effect    | No effect    | No effect          |

Tagged branches must follow the [semantic versioning syntax](https://semver.org/). Tagged versions will not be 
deployed unless they match the validation regex. The version format is as follows:

|   | Development   | Master |
|---|---------------|--------|
|   | x.y.z-alpha.w | x.y.z  |

Following deployment of a release, a Github Release is created, and this should be filled in with the relevant release notes.
