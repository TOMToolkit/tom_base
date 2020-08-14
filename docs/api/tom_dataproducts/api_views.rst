API Views
=========

.. warning:: Check your groups!

    When creating a ``DataProduct`` via the API and you have set ``TARGET_PERMISSIONS_ONLY`` to ``False``, one of the 
    accepted parameters is a list of groups that will have permission to view the ``DataProduct``. If you neglect to 
    specify any groups, your ``DataProduct`` will only be visible to the user that created the ``DataProduct``. Please 
    be sure to specify groups!!

.. tip:: Better API documentation

    The available parameters for RESTful API calls are not available here. However, if you navigate to ``/api/targets/``
    and click the ``OPTIONS`` button, you can easily view all of the available parameters.

.. automodule:: tom_dataproducts.api_views
    :members: