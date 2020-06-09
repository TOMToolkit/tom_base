Using Amazon S3 to Store Data for a TOM
---------------------------------------

If a TOM needs to store a large amount of data, like images or spectra,
it may eventually become impractical to do so on a local hard drive or
network share. This is where cloud storage services like `Amazon
S3 <https://aws.amazon.com/s3/>`__ come in handy. These services allow
you to store large quantities of data at a low cost, while providing
high reliability and feature rich services. In most cases using a cloud
storage system also provides performance and speed increases to your
application.

Configuring the TOM toolkit to store data on Amazon S3 is fairly
straightforward. Once enabled, data product downloads, uploads, and
static assets (images, stylesheets, etc) will be stored in Amazon S3
instead of the local filesystem where your TOM is run.

Sign up for an AWS Account
~~~~~~~~~~~~~~~~~~~~~~~~~~

To use S3, you’ll first need to sign up for an `Amazon Web
Services <https://portal.aws.amazon.com/billing/signup#/start>`__
account. New accounts get access to one year of free tier access which
includes a year of S3 at a max of 5GB. If you’re interested in the cost
beyond 5Gb, try out the `Amazon cost
calculator <https://calculator.s3.amazonaws.com/index.html>`__.

Once you have created an account, you’ll need your access key id and
secret access key. These can be found under your profile settings -> “My
security credentials”. Make sure you save these in a safe place, you’ll
need them later.

Create a bucket
~~~~~~~~~~~~~~~

A bucket is like the highest level folder you can store data in S3. You
should create one for your TOM. Name it whatever you’d like. Most of the
default settings should be fine.

**We need to enable CORS** for JS9 (or any other javascript code that
wants to access our data directly) to work. Under the “Permissions” tab
for your bucket, find the section for “CORS configuration”. In the
editor, paste the following policy:

.. code:: xml

   <?xml version="1.0" encoding="UTF-8"?>
   <CORSConfiguration xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
   <CORSRule>
       <AllowedOrigin>*</AllowedOrigin>
       <AllowedMethod>GET</AllowedMethod>
       <AllowedHeader>*</AllowedHeader>
   </CORSRule>
   </CORSConfiguration>

This policy allows GET requests from anywhere. Feel free to edit it to
match your particular use case specifically.

Configure S3 Storage backend for your TOM
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Now that we have a bucket set up, let’s configure our TOM to use it.
First we need to install two additional python packages. You should add
these to your project’s ``requirements.txt``.:

-  django-storages
-  boto3

Next, we’ll edit our TOM’s ``settings.py`` to use S3 instead of local
storage. Place the following lines somewhere around the existing static
files configuration settings:

.. code:: python

   DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
   STATICFILES_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'

   AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID', '')
   AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRECT_ACCESS_KEY', '')
   AWS_STORAGE_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME', '')
   AWS_S3_REGION_NAME = os.getenv('AWS_S3_REGION_NAME', '')
   AWS_DEFAULT_ACL = None

Notice that these settings get their values via environmental variables.
Depending on how you deploy your TOM, you can set these in a variety of
ways. For example: export AWS_ACCESS_KEY_ID=MyAccessKey would be one way
to set them using Bash.

-  AWS_ACCESS_KEY_ID is your access key id from your security
   credentials.
-  AWS_SECRECT_ACCESS_KEY is your secret access key from your security
   credentials.
-  AWS_STORAGE_BUCKET_NAME is the name you gave to the bucket you
   created.
-  AWS_S3_REGION_NAME is the name of th region you created your bucket
   in.

Once these settings are filled out, your TOM should store all future
data in S3. If you had existing data in your TOM, you should copy it
over to your bucket in the exact same way it was stored locally.

For Heroku Users
~~~~~~~~~~~~~~~~

If you are using Heroku (perhaps by following the `Heroku deployment
guide <https://tomtoolkit.github.io/docs/deployment_heroku>`__) there is
one more additional step. At the very bottom of ``settings.py`` change
the line:

::

   django_heroku.settings(locals())

to:

::

   django_heroku.settings(locals(), staticfiles=False)

This instructs the ``django-heroku`` package to not automatically
configure static files for your TOM (since we are explicitly using S3
now).

Additionally, Heroku makes it easy to set environmental variables. See
`Configuration and Config
Vars <https://devcenter.heroku.com/articles/config-vars>`__.
