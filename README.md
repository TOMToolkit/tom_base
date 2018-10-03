# TOM Toolkit - Base Project
[![Build Status](https://travis-ci.org/TOMToolkit/tom_base.svg?branch=master)](https://travis-ci.org/TOMToolkit/tom_base)

This is the starting point for all new TOMs. This project provides
a base TOM with much of the functionality provided by the TOM Toolkit
enabled by default. If you are looking to start a new TOM this is where
you start.

## Module Descriptions

### TOM Targets
Provides the target storage and import capabilities of the TOM.

### Tom Alerts
A gerneric module for working with astronomical alert streams. Transforms alerts
into targets in the TOM Targets module.

Implementations:
* LCO

### TOM Catalogs
Provides online catalog searching and the ability to import TOM Targets from
search results.

Implementations:
* SIMBAD
* JPL Horizons
* NED

### TOM Observations
A framework for submitting observations and retrieving data products from
astronomical observatories.

Implementations:
* LCO

### TOM Common
Common functions and utilities shared by other modules.

## Quickstart

Please read the
[Getting Started guide](https://tomtoolkit.github.io/docs/getting_started)
