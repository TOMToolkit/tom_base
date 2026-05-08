Configuring a TOM
=================

TOM Settings
------------

TOMs have a number of configurable settings that are needed for various functions.
Since the Toolkit is based on the `Django framework <https://www.djangoproject.com/>`__
most of these options are controlled via the settings.py file.  You'll find this
is created for you when you initialize a new TOM:

.. code::

   mytom/
     | mytom/
         |- settings.py
     ...

The admin of the TOM can edit this file to set the parameters as desired.  A full list of the
configurable options is given :doc:`here</common/customsettings>`

Permissions
-----------

TOM systems can have hundreds or thousands of users and we recognize that sometimes it is desirable to control
who can access what data or functions.  The Toolkit provides fine-grained control over user permissions, as documented
:doc:`here</common/permissions>`.
