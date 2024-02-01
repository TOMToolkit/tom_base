# TOM Toolkit
[![pypi](https://img.shields.io/pypi/v/tomtoolkit.svg)](https://pypi.python.org/pypi/tomtoolkit)
[![run-tests](https://github.com/TOMToolkit/tom_base/actions/workflows/run-tests.yml/badge.svg)](https://github.com/TOMToolkit/tom_base/actions/workflows/run-tests.yml)
[![Codacy Badge](https://app.codacy.com/project/badge/Grade/a09d330b4dca4a4a86e68755268b7da3)](https://www.codacy.com/gh/TOMToolkit/tom_base/dashboard?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=TOMToolkit/tom_base&amp;utm_campaign=Badge_Grade)
[![Coverage Status](https://coveralls.io/repos/github/TOMToolkit/tom_base/badge.svg?branch=main)](https://coveralls.io/github/TOMToolkit/tom_base?branch=main)
[![Documentation Status](https://readthedocs.org/projects/tom-toolkit/badge/?version=stable)](https://tom-toolkit.readthedocs.io/en/stable/?badge=stable)
[![ASCL](https://img.shields.io/badge/ascl-2208.004-blue.svg?colorB=262255)](https://ascl.net/2208.004)

[Documentation](https://tom-toolkit.readthedocs.io/en/latest/)
![logo](tom_common/static/tom_common/img/logo-color.png)

The TOM Toolkit is a web framework for building TOMs: Target and Observation
Managers. TOMs are meant to facilitate collaborative astronomical observing
projects. A typical TOM allows its users to curate target lists, request
observations of those targets at various observatories as well as manage and
organize their data. [Read more](https://tom-toolkit.readthedocs.io/en/stable/introduction/about.html) about TOMs.

## Getting started with the TOM Toolkit
The [getting started guide](https://tom-toolkit.readthedocs.io/en/latest/introduction/getting_started.html)
will guide you through the process of setting up a TOM for the first time.

## Reporting issues/feature requests
Please use the [issue tracker](https://github.com/TOMToolkit/tom_base/issues) to
report any issues or support questions.

## Development Team 
The lead developers of the TOM Toolkit are [William Lindstrom](https://lco.global/people/>)
and [Joey Chatelain](https://sites.google.com/site/josephchatelain>),
professional software developers with the Las Cumbres Observatory software team,
together with [Jon Nation](https://lco.global/people/>), [Curtis McCully](https://lco.global/people/>),
[Matt Daily](https://lco.global/people/>) and [Mark Bowman](https://lco.global/people/>).  [Rachel Street](https://lco.global/user/rstreet/>) is the project's Principle Investigator.
The TOM Toolkit is grateful for the advice and collaboration with [Andy Howell](http://www.dahowell.com/),
[Edward Gomez](https://www.zemogle.net/>), Craig Pellegrino, Jamie Burke and the rest of the LCO Science team.
The [original Toolkit](https://zenodo.org/records/4437764>) was developed by
Austin Riba, David Collom and William Lindstrom.

Our team very much welcome input from the community, and we are grateful to
the following people for their many contributions:
 - Dan Avner, NOIRLab
 - Doug Arnold, Liverpool Telescope
 - Etienne Bachelet, IPAC/Caltech
 - Ezequiel Contreras Martinez, UCSB
 - Griffin Hosseinzadeh, University of Arizona
 - Bryan Miller, Gemini Observatory
 - Brendan Mills, UCSB
 - Julien Peloton, Fink

## Acknowledgements

We hope you find our software useful for your research.  If so, we would be grateful
if you can include a brief acknowledgement in your papers and presentations, for example 
"This research made use of [The TOM Toolkit](https://tom-toolkit.readthedocs.io/)". 
We would also very much appreciate you including a citation to our paper describing 
the Toolkit [Street, R.A. et al., 2018, SPIE, 10707, 11](http://adsabs.harvard.edu/abs/2018SPIE10707E..11S) 
(to export the BibTeX please click [here](https://ui.adsabs.harvard.edu/abs/2018SPIE10707E..11S/exportcitation)).  


## Contributing to the project
If you'd like to contribute to the TOM Toolkit, first of all, thanks! Secondly, we
have a [contribution guide](https://tom-toolkit.readthedocs.io/en/stable/introduction/contributing.html) that
you might find helpful. We are particularly interested in the contribution of
observation and alert modules.

### Community Code of Conduct
We encourage developers to maintian a lively and civil discourse either on github or in our slack workspace.
Please review our [code of conduct](CODE_OF_CONDUCT.md) for information about what is considered unacceptable behavior and how to report it.

## Developer information
For development information targeted at the maintainers of the project, please see [README-dev.md](README-dev.md).

## Plugins

### tom_alerts_dash

The [tom_alerts_dash](https://github.com/TOMToolkit/tom_alerts_dash) plugin adds responsive ReactJS views to the
`tom_alerts` module for supported brokers.

### Antares

The [tom-antares](https://github.com/TOMToolkit/tom_antares) plugin adds support
for querying the Antares broker for targets of interest.

### tom_nonsidereal_airmass

The [tom_nonsidereal_airmass](https://github.com/TOMToolkit/tom_nonsidereal_airmass) plugin provides a templatetag
that supports plotting for non-sidereal objects. The plugin is fully supported by the TOM Toolkit team; however,
non-sidereal visibility calculations require the PyEphem library, which is minimally supported while its successor
is in development. The library used for the TOM Toolkit sidereal visibility, astroplan, does not yet support
non-sidereal visibility calculations.

### tom-lt

This module provides the ability to submit observations to the Liverpool Telescope Phase 2 system. It is in a very alpha
state, with little error handling and minimal instrument options, but can successfully submit well-formed observation
requests.

[Github](https://github.com/TOMToolkit/tom_lt)

### tom_registration

The [tom_registration](https://github.com/TOMToolkit/tom_registration) plugin introduces support for two TOM registration
flows--an open registration, and a registration that requires administrator approval.

## About the TOM Toolkit

The TOM Toolkit is managed by Las Cumbres Observatory, with generous
financial support from the [National Science Foundation](https://www.nsf.gov/>) grant 2209852.
We are also grateful for support from the [Heising-Simons Foundation](https://hsfoundation.org>) 
and the [Zegar Family Foundation](https://sites.google.com/zegarff.org/site>) at the start
of the project.  
