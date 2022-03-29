Example TOMs
------------

SNEx
~~~~

The `Supernova Exchange <https://supernova.exchange/public/>`__ is an
interface for viewing and sharing observational data of supernovae, and
for requesting and managing observations with the Las Cumbres
Observatory network. In order to make it more maintainable, it is being
rewritten from scratch using the TOM Toolkit, which has already resulted
in orders of magnitude fewer lines of code. The code can be found and
referenced on `Github <https://github.com/jfrostburke/snex2/>`__.

Asteroid Tracker
~~~~~~~~~~~~~~~~

`Asteroid Tracker <https://asteroidtracker.lco.global/>`__ is an
educational TOM built by Edward Gomez for Asteroid Day. It allows 
students and teachers to submit one-click observations of specific 
asteroids and see the resulting images. Originally built from scratch, 
it’s being rewritten using the TOM Toolkit, which will allow the 
underlying TOM to be used with multiple front-ends for completely 
different educational purposes.

Microlensing TOM (MOP)
~~~~~~~~~~~~~~~~~~~~~~

The `Microlensing Observing Platform <https://mop.lco.global>`__ is the core interface of the OMEGA Key Project. It is designed to harvest and prioritize microlensing events from various surveys, then submit additional observations with the Las Cumbres Observatory telescopes automatically.


PhotTOM
~~~~~~~

The `ROME/REA TOM <https://github.com/rachel3834/romerea_phot_tom>`__ is
being built to manage ROME/REA photometry for the `LCO key project of
the same name <https://robonet.lco.global/>`__.

Calibration TOM
~~~~~~~~~~~~~~~

LCO is rewriting an existing piece of software that automatically
schedules nightly telescope calibrations using the TOM Toolkit called
the `Calibration TOM <https://github.com/LCOGT/calibration-tom/>`__.

PANOPTES TOM
~~~~~~~~~~~~

The `PANOPTES TOM <https://github.com/panoptes/panoptes-tom>`__ is being 
built to enable their community to coordinate observations for the 
`PANOPTES citizen science project <https://projectpanoptes.org/>`__, which 
aims to detect transiting exoplanets.

AMON TOM
~~~~~~~~

Black Hole TOM
~~~~~~~~~~~~~~
Black Hole TOM (BHTOM) aims at coordinating the photometric and spectroscopic follow-up observations of targets requiring long-term monitoring. This includes long lasting microlensing events reported by Gaia and other surveys, likely caused by galactic black holes. The system lists targets according to their priorities and allows for triggering robotic observations. It also allows users of any partner observatory to submit their raw photometric and spectroscopic data, which gets automatically processed and calibrated. BHTOM is developed as part of the Time Domain Astronony work package of the European OPTICON grant by the team at the University of Warsaw, Poland, with support from LCO. Website: http://visata.astrouw.edu.pl:8080

ALeRCE TOM
~~~~~~~~~~

The `ALeRCE TOM <https://tom.alerce.online/>`__ is used by the ALeRCE team to submit follow-up observations on ZTF targets from the ALeRCE broker module, which uses the `ALeRCE Database API <http://alerce.science/services/ztf-db-api/>`__.

ANTARES TOM
~~~~~~~~~~~

The `ANTARES TOM <https://tom.antares.noirlab.edu/>`__ is built by the ANTARES team to connect to the
`ANTARES alert broker <https://antares.noirlab.edu/>`__ via the ANTARES broker module.
In addition, the ANTARES TOM can gather public light curves from ZTF and spectra from TNS
for each target in an automatic and programmatic manner
(see `example notebook <https://github.com/lchjoel1031/ANTARES/blob/main/ANTARES-TOM-API.ipynb>`__).
It is being used by the ANTARES team to share target information and coordinate follow-up with facilities
from the Astronomical Event Observatory Network (`AEON <https://noirlab.edu/public/projects/aeon/>`__).

Others
~~~~~~

There are a few other TOMs in development that we’re aware of, but if
you’re developing a TOM, feel free to contribute to this page, or let us
know and we’ll take care of it for you.
