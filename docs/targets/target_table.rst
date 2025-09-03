Customizing the Target List Table
---------------------------------

The TOM Toolkit provides some functions for customizing the target list table without requiring
custom templates or other code.

Changing Which Columns Are Displayed
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The :doc:`TARGET_LIST_COLUMNS <../common/customsettings>` settings allows defining which columns are displayed on the target
list page. The default value is:

.. code-block:: python

    TARGET_LIST_COLUMNS = [
        "name", "type", "observations", "saved_data"
    ]


For example, to display the target's RA And DEC as the last two columns in the table:

.. code-block:: python

    TARGET_LIST_COLUMNS = [
        "name", "type", "observations", "saved_data", "ra", "dec"
    ]


Valid values to include in  `TARGET_LIST_COLUMNS` consist of:

1. Attributes or properties of the Target Model. See :doc:`Adding Custom Target Fields <target_fields>` to
learn how to add custom fields to a Target Model.

2. Extra Fields or Tags associated with the Target Model. Note that tags that are not present for
an individual target will appear empty.

3. The special fields:

    - `name`: The name(s) of the target, looks up additional names.
    - `saved_data`: A count of the number of saved datums.
    - `observations`: A count of the number of observations.
