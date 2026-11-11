ALeRCE: ZTF and LSST
--------------------

The ALeRCE data service queries the `ALeRCE <https://alerce.online/>`_ broker for objects from
both ZTF and the Rubin Observatory's LSST. Choose the survey with the **Survey** field on the
query form.

How ALeRCE is queried
*********************

* **ZTF** searches use the ALeRCE REST API through the ``alerce`` Python client, as before.
* **LSST** searches, and the classifier lists for both surveys, use ALeRCE's
  `TAP service <https://tap.alerce.online/tap>`_ through ``pyvo``. The REST API can list LSST
  objects, but it cannot yet filter them by classifier or list the LSST classifiers, and asteroid
  (ssObject) searches need the MPC orbits that are only available through TAP.
* **Light curves** for both surveys come from the REST API.

If the TAP service is unavailable, the query form still loads without the classifier fields, and
LSST searches report an error instead of failing the page.

Searching for LSST objects
**************************

With **Survey** set to LSST, choose an **LSST Object Type**:

``diaObject``
    A static-sky transient or variable, for example a supernova candidate.

``ssObject``
    A known Solar System object, linked by the MPC to an orbit.

The **Object ID** field takes a diaObjectId, an ssObjectId, or an asteroid designation such as
``2010 WX64``. A designation is looked up in ALeRCE's copy of the MPC orbits, which takes about
a second. Without an Object ID, the cone search, first and last detection MJD, and number of
detections fields filter the search, as they do for ZTF. There are also three LSST-specific
options:

* **Classifiers** filter diaObjects by class and minimum probability, for example ``SN`` from
  ``stamp_classifier_rubin_beta``. ssObjects are not offered here, because ALeRCE assigns every
  known ssObject the asteroid class with probability 1 rather than classifying it.
* **Max. Detection Time Span (days)** limits the time between the first and last detection.
  Together with the stamp classifier's asteroid class, a span of less than a day finds candidate
  new moving objects that are not yet linked to an ssObject.
* **Max. Results**, **Sort By** and **Sort Order** control the size and order of the results.
  When you filter by classifier, the limit applies to each classifier separately, and results
  are sorted by probability by default.

Each result links to the object's page on the ALeRCE Explorer.

Creating targets
****************

* A **diaObject** becomes a sidereal target named by its diaObjectId, at ALeRCE's mean position.
* An **ssObject** becomes a non-sidereal target named by its ssObjectId, with orbital elements
  taken from its MPC orbit. Bound orbits use the ``MPC_MINOR_PLANET`` scheme; unbound ones use
  ``MPC_COMET``. The target's aliases include its provisional designation and, where the MPC has
  assigned them, its permanent number, name and any secondary designations. That way you can find
  it under whichever name you know.

Photometry
**********

LSST light curves report difference-image PSF fluxes in nJy. These are converted to AB
magnitudes, with a zero point of 31.4, and their times are converted from TAI to UTC. Detections
with zero or negative difference flux have no magnitude and are skipped. LSST photometry is
recorded with the telescope ``Rubin`` and the instrument ``LSSTCam``.

Updating the data for a target again leaves the photometry already stored unchanged, even if ALeRCE
has since revised a measurement's uncertainty.

Updating targets from other sources
***********************************

A target doesn't have to come from ALeRCE for ALeRCE to update its data. The data service finds
the ALeRCE object from the target's name and aliases, in this order:

#. A name that is already a ZTF object ID or an LSST diaObjectId/ssObjectId.
#. A TNS name (e.g. ``SN 2025abc``), resolved to its ZTF or LSST internal name through TNS.
   This needs the TNS data service to be configured; otherwise TNS names are skipped.
#. An MPC designation (e.g. ``2010 WX64``), resolved to its LSST ssObjectId.

This means, for example, that an asteroid target created from the MPC can pick up its LSST
photometry.
