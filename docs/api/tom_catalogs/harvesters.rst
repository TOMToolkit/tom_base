Harvesters
==========

********************
Base Harvester Class
********************

.. automodule:: bhtom_catalogs.harvester
    :members:


************
JPL HORIZONS
************

.. automodule:: bhtom_catalogs.harvesters.jplhorizons
    :members:


*******************
Minor Planet Center
*******************

Please note that there is an astroquery bug in ``0.4.1`` that breaks the ``MPCHarvester``. In order to resolve this, 
either remove the MPC module from ``settings.TOM_HARVESTER_CLASSES``, or install a pre-release version of 
astroquery using the following command:

.. code::

    pip install astroquery --upgrade --pre --use-deprecated=legacy-resolver


.. automodule:: bhtom_catalogs.harvesters.mpc
    :members:


***
NED
***

.. automodule:: bhtom_catalogs.harvesters.ned
    :members:


******
SIMBAD
******

.. automodule:: bhtom_catalogs.harvesters.simbad
    :members:


*********************
Transient Name Server
*********************

.. automodule:: bhtom_catalogs.harvesters.tns
    :members: