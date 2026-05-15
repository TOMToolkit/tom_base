Deploying your TOM Online
=========================

.. toctree::
  :maxdepth: 2
  :hidden:

  deployment_tips
  deployment_heroku
  amazons3
  encryption

Once you’ve got a TOM up and running on your machine, you’ll probably want to deploy it somewhere so it is permanently
accessible by you and your colleagues.

:doc:`General Deployment Tips <deployment_tips>` - Read this first before deploying your TOM for others to use.

:doc:`Deploy to Heroku <deployment_heroku>` - Heroku is a PaaS that allows you to publicly deploy your web applications without the need for managing the infrastructure yourself.

:doc:`Using Amazon S3 to Store Data for a TOM <amazons3>` - Enable storing data on the cloud storage service Amazon S3 instead of your local disk.

:doc:`Configuring the Master Encryption Key <encryption>` - How to set ``TOMTOOLKIT_DEK_ENCRYPTION_KEY`` across deploy environments and migrate off the public default.