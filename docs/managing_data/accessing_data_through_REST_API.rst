Accessing data through the REST API
---------------------------------------

`Django REST Framework (DRF) <https://www.django-rest-framework.org/>`_ is built into TOM Toolkit.
This allows you to access the data in your TOM's database through a REST API.

.. note::
    If the ``DEFAULT_AUTHENTICATION_CLASSES`` key is not present in your
    ``settings.REST_FRAMEWORK`` configuration dictionary, then you get
    ``SessionAuthentication``, and ``BasicAuthentication`` because that's the DRF default.
    To add ``TokenAuthentication``, your ``DEFAULT_AUTHENTICATION_CLASSES`` should look like this:

    .. code:: python

        REST_FRAMEWORK = {
            'DEFAULT_AUTHENTICATION_CLASSES': [
                'rest_framework.authentication.TokenAuthentication',
                'rest_framework.authentication.SessionAuthentication',
                'rest_framework.authentication.BasicAuthentication',
            ],
            # ... your existing REST_FRAMEWORK settings ...
        }

    - ``BasicAuthentication`` is used when you send username/password credentials in the ``AuthorizationHeader`` of an HTTP request.
    - ``SessionAuthentication`` uses a cookie and CSRF protection to access the API from your TOM in a browser while logged in.
    - ``TokenAuthentication`` uses your ``API Token`` available from the User Info of your User Profile of your TOM.

    To see ``SessionAuthentication`` in action, while logged into your TOM, point your browser to the ``/api/`` endpoint.
    This is the DRF API root. We'll show ``BasicAuthentication`` and ``TokenAuthentication`` in use below.


Quick start: querying targets with curl
#########################################

The examples below query the targets endpoint on a TOM running locally at
``http://127.0.0.1:8888`` with a user ``tom_user_1``. Adjust the host, port and
username to match your deployment.

Basic Authentication
*************************************************

.. code:: bash

    curl -u tom_user_1  http://127.0.0.1:8888/api/targets/

You'll be prompted for ``tom_user_1``'s password.
You should receive a JSON blob with target data. Don't forget that trailing ``/``.

This is ``BasicAuthentication``: ``curl`` sends the username and password in the
``AuthenticationHeader`` of the HTTP request. 

Token Authentication
*************************************************

Every user has a personal API token, shown as **API Token** on their
**User Profile** page. A token suits scripts and cron jobs because it
needs no interactive prompt. Secure your API token as you would a password.

Rather than pass in a username and be prompted for a password, we'll authenticate
by sending the token in an ``Authorization`` header:

To keep the API token out of your command history and scripts, export it as an
environment variable once and reference it in the header:

.. code:: bash

    export TOM_API_TOKEN="API-token-copied-from-User-Profile"
    curl -H "Authorization: Token $TOM_API_TOKEN" http://127.0.0.1:8888/api/targets/


Next Step: querying targets in code
#########################################

The same requests work from Python with the
`requests <https://requests.readthedocs.io/>`_ library.

Basic Authentication
*************************************************

Pass your username and password as the ``auth`` tuple:

.. code:: python

    import requests

    response = requests.get(
        'http://127.0.0.1:8888/api/targets/',
        auth=('tom_user_1', 'your-password'),
    )
    targets = response.json()

``targets`` now holds the same JSON you got back from ``curl``.

Token Authentication
*************************************************

Send your API token in an ``Authorization`` header instead. The API token
substitutes for the `BasicAuthentication` username and  password.

.. code:: python

    import requests

    headers = {'Authorization': 'Token API-token-copied-from-User-Profile'}
    response = requests.get('http://127.0.0.1:8888/api/targets/', headers=headers)
    print('status:', response.status_code)
    print('targets:  ', response.json())

Don't hard-code real credentials: read the password or token from an environment
variable (e.g. ``os.environ['TOM_API_TOKEN']``) as in the ``curl`` example above.

Obtaining your API Token programmatically
#########################################

Above, we've seen how to access your TOM's data using ``curl`` and ``Python``,
via ``BasicAuthentication`` (username, password) and ``TokenAuthentication`` (API Token).

Your API Token is available from the User Info card of your User Profile. (You may rotate
your API Token from the User Profile update page (available from the pencil (edit) icon of
the User Info card). Rotating your API token is analogous to, but separate from, changing
your password).

Here we show how to obtain your API Token programmatically. Django REST Framework
provides the mechanism for this and it is available at a the ``api/token-auth`` endpoint.

Using curl
******************************************

Using the same assumptions as above with respect to ``host``, ``port``, ``username``,
and ``password``:

.. code:: bash

    curl --request POST http://127.0.0.1:8888/api/token-auth/ \
         --header "Content-Type: application/json" \
         --data '{"username": "tom_user_1", "password": "your-password"}'

Things to note here:
 - This is a ``POST`` request.
 - The ``Content-Type`` specified in the request header lets DRF know to expect a JSON payload.
 - The ``BasicAuthentication`` credentials are passed as the JSON payload of the request.

The ouput you see will be JSON to stdout of the form ``{"token":"3bc76a8b6400182d617e9a1ce75dfa92d87412a0"}``.

Using Python
******************************************
Here is the equivalent request made from Python code:

.. code:: python

    import requests

    response = requests.post(
        'http://127.0.0.1:8888/api/token-auth/',
        json={'username': 'tom_user_1', 'password': 'your-password'},
    )
    print('status:', response.status_code)
    print('json:  ', response.json())  # {"token":"3bc76a8b6400182d617e9a1ce75dfa92d87412a0"}


Further details can be found in the `DRF Authentication API Guide <https://www.django-rest-framework.org/api-guide/authentication/>`_.
