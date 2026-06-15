Commands
========

****************
tom_dataproducts
****************

 - `downloaddata.py` - Downloads available data for all completed observations.

 - `updatereduceddata.py` - Gets and updates time-series data for a target with data extracted from data services. This will search existing data for sources that match installed data services and check those data services for new data.


****************
tom_dataservices
****************

 - `listqueries.py` - Creates a table of saved DataService queries.

 - `rundataquery.py` - Runs saved dataservice queries and saves the results as Targets.


****************
tom_observations
****************

 - `runcadencestrategy.py` - Entry point for running cadence strategies.

 - `updatestatus.py` - Updates the status of each observation request in the TOM. Target id can be specified to update the status for all observations for a single target.


***********
tom_targets
***********

 - `converttargetextras.py` - A Helper command to convert target extras into UserDefinedTarget Fields

 - `setdefaultextras.py` - Adds the default TargetExtra value to all Targets that do not have the provided TargetExtra
