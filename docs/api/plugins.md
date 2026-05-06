TOM Toolkit Plugins
-------------------

We aim to keep the TOM as lightweight and flexible as possible, and we 
recognise that every team has their own science goals and often need 
different functions.  These often come with added dependencies.  

Rather than require users to support all dependencies from all possible 
functions, we support a range of optional plugin modules for the Toolkit. 
These range from adding the ability to interface with additional
observatories, to providing additional plotting or data analytics functionality.

### [tom_hermes](https://github.com/TOMToolkit/tom_hermes)

The [Hermes](https://hermes.lco.global) service provides a archive of 
astronomical alerts.  This plugin allows TOM users to query Hermes and share
data with the service.  

### [tom_fink](https://github.com/TOMToolkit/tom_fink)

[Fink](https://fink-broker.org/) is an alert broker service.  This plugin 
enables users to query this service and harvest alert information. 

### [tom_antares](https://github.com/TOMToolkit/tom_antares)

The [tom-antares](https://github.com/TOMToolkit/tom_antares) plugin adds support
for querying the [ANTARES](https://antares.noirlab.edu/) broker for targets of interest.

### [tom_app_template](https://github.com/TOMToolkit/tom_app_template)

This repository is designed to provide an example template for TOM users 
wishing to develop their own TOM app.  

### [tom_jpl](https://github.com/TOMToolkit/tom_jpl)

The Jet Propulsion Laboratory provides a number of services supporting 
Solar System science.  This plugin provides a TOM interface to JPL's 
[SCOUT](https://cneos.jpl.nasa.gov/scout/intro.html) service.  

### [tom_eso](https://github.com/TOMToolkit/tom_eso)

This plugin enables users to compose and submit observation requests to 
telescopes at the [European Southern Observatory](https://www.eso.org/public/). 

### [tom_regions](https://github.com/TOMToolkit/tom_regions)

This plugin allows a TOM to store sky regions defined from Multi-Order 
Coverage maps. 

### [tom_registration](https://github.com/TOMToolkit/tom_registration)

The [tom_registration](https://github.com/TOMToolkit/tom_registration) plugin introduces support for two TOM registration
flows--an open registration, and a registration that requires administrator approval.

### [tom_tns](https://github.com/TOMToolkit/tom_tns)

This plugin enables TOMs to report transient classifications to 
the [Transient Name Server](https://www.wis-tns.org/).

### [tom_alertstreams](https://github.com/TOMToolkit/tom_alertstreams)

Apache Kafka is widely used in astrophysics for the dissemination of 
alert packages.  This plugin enables a TOM system to listen to user-configured 
alerts streams. 

### [tom_demoapp](https://github.com/TOMToolkit/tom_demoapp)

This TOM application is designed to demonstrate how users can develop 
their own TOM applications and integrate them with their TOM systems. 

### [tom_nonlocalisedevents](https://github.com/TOMToolkit/tom_nonlocalizedevents)

Various events in astrophysics are hard to localise, for example gravitational wave
 or neutrino detections.  This app allows the TOM to recognise that a
given event may be associated with a number of candidates, and provides 
custom views designed to support this workflow.

### [tom_swift](https://github.com/TOMToolkit/tom_swift)

The Neil Gehrels Swift Observatory is a space telescope offering UV/Visible and 
X-ray instrumentation and rapid response capabilities.  This plugin 
enables TOM users to submit requests for Target of Opportunity observations 
with this spacecraft. 

### [tom_classifications](https://github.com/TOMToolkit/tom_classifications)

This app provides a number of data visualization tools for inspecting alert 
data from multiple brokers. 

### [tom_keck](https://github.com/TOMToolkit/tom_keck)

Application to enable requests for Target of Opportunity observations 
to be submitted to the [Keck Observatories](https://keckobservatory.org/).  
Note: to be integrated with [AEONlib](https://github.com/AEONplus/AEONlib). 

### [tom-lt](https://github.com/TOMToolkit/tom_lt)

This module provides the ability to submit observations to the 
[Liverpool Telescope](https://telescope.livjm.ac.uk/) Phase 2 system. It is in a very alpha
state, with little error handling and minimal instrument options, but can successfully submit well-formed observation
requests.

### [dockertom](https://github.com/TOMToolkit/dockertom)

This repository demonstrates how to package a TOM system in a docker container, 
which is often required for deployment.  

### [tom-toolkit_component_lib](https://github.com/TOMToolkit/tom-toolkit-component-lib)

Demonstration of how Javascript front-end components can be integrated with 
a TOM. 

### [tom_scimma](https://github.com/TOMToolkit/tom_scimma)

This app enables a TOM to subscribe to the Hopskotch alert stream developed 
by the Scalable Cyberinfrastructure to support Multi‑Messenger Astrophysics 
([SCiMMA](https://scimma.org/)) project.

### [tom_dash](https://github.com/TOMToolkit/tom_dash)

This module demonstrates how [Plotly-Dash](https://dash.plotly.com/) components can be added to a 
TOM for data exploration and visualization. 

### [tom_gemini_community](https://github.com/TOMToolkit/tom_gemini_community)

TOM module to enable observations to be submitted to the 
[Gemini Telescope's](http://www.gemini.edu/) Phase 2 system. 

### [tom_nonsidereal_airmass](https://github.com/TOMToolkit/tom_nonsidereal_airmass)

The [tom_nonsidereal_airmass](https://github.com/TOMToolkit/tom_nonsidereal_airmass) plugin provides a templatetag
that supports plotting for non-sidereal objects. The plugin is fully supported by the TOM Toolkit team; however,
non-sidereal visibility calculations require the PyEphem library, which is minimally supported while its successor
is in development. The library used for the TOM Toolkit sidereal visibility, astroplan, does not yet support
non-sidereal visibility calculations.

### [herokutom](https://github.com/TOMToolkit/herokutom)

This repository demonstrates how a TOM system can be deployed to a public 
server using the [Heroku platform](https://www.heroku.com/).  

## Archived plugins

The following plugins are available but not currently supported.  In some 
cases this is because the functionality has been integrated with the 
base Toolkit. 

### [tom_alerts_dash](https://github.com/TOMToolkit/tom_alerts_dash)

The [tom_alerts_dash](https://github.com/TOMToolkit/tom_alerts_dash) plugin adds responsive ReactJS views to the
`tom_alerts` module for supported brokers.  This module has been superceded 
by tom_dataservices in v3.0.0.  

### [tom_publications](https://github.com/TOMToolkit/tom_publications)

This application prototyped tools to enable users to output latex-formatted 
data from their TOM system.  
