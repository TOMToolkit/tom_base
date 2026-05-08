Deploying your TOM Online
=========================

Once you’ve got a TOM up and running on your machine (aka ``localhost``), it's advantageous to deploy to a
webhosting service so that it is accessible by you and your colleagues worldwide.

There are a number of different ways of doing this, either by hosting the TOM on a local webserver, or by
deploying it to a Cloud-based service.

Whichever option you choose, there are some essential decisions to make, including some security settings that it's
important to get right.  :doc:`General Deployment Tips </deployment/deployment_tips>` covers these fundamentals.

Dockerizing your TOM
--------------------

Docker is a software packaging system which creates a container that ensures the software has a well-defined
environment in which to run -- including all necessary dependencies.  This has become widely used and is often
a necessary first step to deploying your TOM.  An example repository of a dockerized TOM system can be found
`here <https://github.com/TOMToolkit/dockertom>`_ for reference.

Local Server
------------

Many institutions have their own in-house servers on which they host their own websites.  If that is the case at
your institution, then talk to your IT department about hosting your TOM from a local server - every institution
has a distinct configuration.

Cloud Server
------------

There are a number of Cloud service providers that can host a TOM system, including Heroku, Google Cloud, Azure and
Amazon Web Service (AWS).  It's worth noting that while Github offers the github.io service, this is designed for
relatively static content in Markdown format rather than database-driven services like a TOM system.

Heroku offers one of the most straight-forward deployment workflows, without the need for managing the infrastructure yourself,
so we use this as a guide to the process in :doc:`Deploy to Heroku </deployment/deployment_heroku>`.

Data storage
------------

Cloud providers also offer general-purpose data storage, which is often value for TOM-related data products.
:doc:`Using Amazon S3 to Store Data for a TOM </deployment/amazons3>` demonstrates how to enable storing data on the cloud storage
service Amazon S3 instead of your local disk.