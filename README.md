# TOM Toolkit - Base Project

This is the starting point for all new TOMs. This project provides
a base TOM with much of the functionality provided by the TOM Toolkit
enabled by default. If you are looking to start a new TOM this is where
you start.

## Included Functionality

* Observation Targets ([tom_targets](https://github.com/TOMToolkit/tom_targets/))
* LCO Observatory Support ([tom_lco](https://github.com/TOMToolkit/tom_lco))
* SALT Observatory Support ([tom_lco](https://github.com/TOMToolkit/tom_salt))
* MPC Catalog Access ([tom_mpc](https://github.com/TOMToolkit/tom_mpc))
* JPL Horizons Catalog Access ([tom_jplhorizons](https://github.com/TOMToolkit/tom_jplhorizons))
* ExoFOP Catalog Access ([tom_exofop](https://github.com/TOMToolkit/tom_exofop))

## Quickstart

    pip install -r requirements.txt
    ./manage.py migrate
    ./manage.py runserver

Read the [full documentation](https://tomtoolkit.github.io)


