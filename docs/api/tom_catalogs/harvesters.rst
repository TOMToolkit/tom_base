Harvesters
==========

********************
Base Harvester Class
********************

.. automodule:: tom_catalogs.harvester
    :members:


************
JPL HORIZONS
************

.. automodule:: tom_catalogs.harvesters.jplhorizons
    :members:


*******************
Minor Planet Center
*******************

Please note that there is an astroquery bug in ``0.4.1`` that breaks the ``MPCHarvester``. In order to resolve this, 
either remove the MPC module from ``settings.TOM_HARVESTER_CLASSES``, or install a pre-release version of 
astroquery using the following command:

.. code::

    pip install astroquery --upgrade --pre --use-deprecated=legacy-resolver


There is also an alternative interface which uses the more modern `MPC Explorer <https://data.minorplanetcenter.net/explorer/>`_
API interface which can be enabled by adding ``tom_catalogs.harvesters.mpc.MPCExplorerHarveter`` to  ``settings.TOM_HARVESTER_CLASSES``.
As of 2025 January, the MPC Explorer interface is still listed as beta by the MPC and lacks support for comets and natural satellites.

.. automodule:: tom_catalogs.harvesters.mpc
    :members:


***
NED
***

.. automodule:: tom_catalogs.harvesters.ned
    :members:


******
SIMBAD
******

.. automodule:: tom_catalogs.harvesters.simbad
    :members:


*********************
Transient Name Server
*********************

.. automodule:: tom_catalogs.harvesters.tns
    :members: