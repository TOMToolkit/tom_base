Building Interactive HTMX Tables
-----------------------------------

TOM Toolkit provides base classes for building interactive data tables with
filtering, sorting, and pagination that avoid full-page reloads using
`HTMX <https://htmx.org/>`_.

Three model-independent base classes in ``tom_common.htmx_table`` handle
common concerns so that creating a new HTMX-driven table for any model is largely
a configuration task. The provided classes are:

 - ``HTMXTable`` - This class extends ``django_tables2.Table``
   to add HTMX attributes to certain HTML elements, handle checkboxes, etc.
   Your subclass will define your table, specifying the Model supplying data to your
   table and the fields that will be displayed.

 - ``HTMXTableFilterSet`` - Your subclass will define data filters and add HTMX
   elements to update your table as the filters change.

 - ``HTMXTableViewMixin`` - This mix-in class must be added to your ListView subclasses
   that present their data in ``HTMXTable`` subclasses. It recognizes AJAX (HTMX) requests
   and adds pagination data to your ListView's context.

Creating a Basic HTMX Table for Your Model
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This section walks through the three pieces you need to get started: a Table class, a View, and a template. 
The `Target list page <https://tom-demo.lco.global/targets/>`_ provides an example implementation for each step.


Step 1: Define the Table
^^^^^^^^^^^^^^^^^^^^^^^^^

A ``tables.py`` module in your app or ``custom_code`` is good place to
define your ``HTMXTable``.
Subclass ``HTMXTable`` in ``tables.py``. The base class
provides the Bootstrap/HTMX template, row-selection checkboxes, and
all the ``Meta.attrs`` needed for sorting and pagination to work via
HTMX. [1]_ Your subclass ``Meta.attrs`` must specify the Model and Fields
to be displayed.

.. code-block:: python
    :caption: myapp/tables.py
    :linenos:

    from tom_common.htmx_table import HTMXTable  # HTMXTable is a django_tables2.Table subclass
    from myapp.models import Observation  # for example

    class ObservationTable(HTMXTable):

        # linkify makes the entry in the "name" column a link to the model detail page.
        name = tables.Column(
            linkify=True,
            attrs={"a": {"hx-boost": "false"}}
        )

        class Meta(HTMXTable.Meta):
            model = Observation
            fields = ['selection', 'name', 'date', 'status']

NOTES:

- *Line 14:* Include ``'selection'`` in ``fields`` to enable row-selection checkboxes. All of the other fields should
  be model fields for your chosen model.

- *Line 8:* Use ``linkify=True`` on a column to turn cell values into links to the
  object's detail page. If your model does not have a detail page, or a ``get_absolute_url()`` defined, including this
  will result in a `TypeError`.

- *Line 9:* The ``hx-boost="false"``
  attribute ensures that clicking the link triggers a normal page navigation
  (to the object's detail page) rather than being intercepted by HTMX. [2]_

See the example in `tom_targets/tables.py <https://github.com/TOMToolkit/tom_base/tree/dev/tom_targets>`_.


Step 2: Update the View
^^^^^^^^^^^^^^^^^^^^^^^^^

Add ``HTMXTableViewMixin`` *before* your existing List (or Filter) view. The mixin extends
``django_tables2.SingleTableMixin`` and handles HTMX request detection
and template selection. It also adds ``record_count`` and
``empty_database`` to the template context. [4]_

.. code-block:: python
    :caption: myapp/views.py
    :linenos:

    from django.views.generic.list import ListView

    from tom_common.htmx_table import HTMXTableViewMixin
    from myapp.models import Observation
    from myapp.tables import ObservationTable

    class ObservationListView(HTMXTableViewMixin, ListView):
        template_name = 'myapp/observation_list.html'
        model = Observation
        table_class = ObservationTable
        paginate_by = 20
        ordering = ['-date']

NOTES: 

If you are updating an existing List/FilterView then the `HTMXTableViewMixin`, line 11, defining `table_class` and the
appropriate imports are the only changes you should need to make.

See the example in `tom_targets/views.py <https://github.com/TOMToolkit/tom_base/blob/dev/tom_targets/views.py>`_.

Step 3: Set Up the Template
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You will need to create or modify the template page used to display your table.
The bootstrap HTMX template (for sorting and pagination) and a default
partial template are provided by the base classes.

Table page template
===================

The main table template includes a progress indicator and the
table container.

The Table container includes the default partial template for generating the table. We will discuss overriding 
this a little later.

.. code-block:: html+django
    :caption: myapp/templates/myapp/observation_list.html
    :linenos:

    {% extends 'tom_common/base.html' %}

    {% block title %}Observations{% endblock %}

    {% block content %}
    <div class="row">
      <div class="col-md-12">
        <h2>{{ record_count }} Observation{{ record_count|pluralize }}</h2>

        {# Progress indicator (CSS provided by TOM Toolkit base template) #}
        <div class="progress">
            <div class="indeterminate"></div>
        </div>

        {# Table container -- this is the HTMX swap target #}
        <div class="table-container">
            {% include table.get_partial_template_name %}
        </div>
      </div>
    </div>
    {% endblock content %}

See the reference implementation in
``tom_targets/templates/tom_targets/target_list.html``.

At this point you should have an interactive table with sortable columns and pagination!

Add Search Bar
~~~~~~~~~~~~~~~
Next we will add search functionality to our table. We will start with a simple search bar and add more features later.
This requires 3 steps:

 - Creating the basic FilterSet
 - Adding the FilterSet to our View
 - Adding the Form to our Template

Step 1: Create the FilterSet
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Subclass ``HTMXTableFilterSet`` from ``tom_common.htmx_table``. The base
class provides a General Search text field (``query``) with debounced
HTMX attributes already configured. This general search will query all non-ForeignKey fields in your model by default.
You can override ``general_search()`` with your model-specific search logic if you require more advanced functionality.

.. code-block:: python
    :caption: myapp/filters.py
    :linenos:

    from tom_common.htmx_table import HTMXTableFilterSet
    from myapp.models import Observation

    class ObservationFilterSet(HTMXTableFilterSet):

        class Meta:
            model = Observation
            fields = []

NOTES:

- The General Search fires after a short (debounced) pause in typing.

- For now we are going to leave the fields empty. If you want to add more complex filtering options, we will add
  fields here later.

Step 2: Add FilterSet to the View
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Next we need to add the FilterSet to the view.
Since we are adding filters, we can no longer rely on a simple ListView, and must use a FilterView instead.
Note the highlighted changes.

.. code-block:: python
    :caption: myapp/views.py
    :linenos:
    :emphasize-lines: 1, 6, 8, 12

    from django_filters.views import FilterView

    from tom_common.htmx_table import HTMXTableViewMixin
    from myapp.models import Observation
    from myapp.tables import ObservationTable
    from myapp.filters import ObservationFilterSet

    class ObservationListView(HTMXTableViewMixin, FilterView):
        template_name = 'myapp/observation_list.html'
        model = Observation
        table_class = ObservationTable
        filterset_class = ObservationFilterSet
        paginate_by = 20
        ordering = ['-date']


Step 3: Add your form to the Template
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Finally, we will head back to our primary table page template and insert the form with the relevant HTMX.

.. code-block:: html+django
    :caption: myapp/templates/myapp/observation_list.html
    :linenos:
    :emphasize-lines: 2, 11-19

    {% extends 'tom_common/base.html' %}
    {% load crispy_forms_tags %}

    {% block title %}Observations{% endblock %}

    {% block content %}
    <div class="row">
      <div class="col-md-12">
        <h2>{{ record_count }} Observation{{ record_count|pluralize }}</h2>

        <hr>
        {# Filter form -- id must match hx-include in the Table's Meta.attrs #}
        <form id="filter-form" class="mb-3"
              hx-get="{{ request.get_full_path }}"
              hx-target="div.table-container"
              hx-swap="outerHTML"
              hx-indicator=".progress">
            {% crispy filter.form %}
        </form>

        {# Progress indicator (CSS provided by TOM Toolkit base template) #}
        <div class="progress">
            <div class="indeterminate"></div>
        </div>

        {# Table container -- this is the HTMX swap target #}
        <div class="table-container">
            {% include table.get_partial_template_name %}
        </div>
      </div>
    </div>
    {% endblock content %}

Notes:

- *Line 13:* The ``id="filter-form"`` must match the ``"hx-include": "#filter-form"``
  in ``HTMXTable.Meta.attrs`` so that filter values are preserved during
  sorting and pagination. This is handled in the base ``HTMXTable`` but these values could be overwritten if multiple
  tables were being used on the same page. [5]_

Now there should be a General Search Bar above your table:

|image0|

Customization Options
~~~~~~~~~~~~~~~~~~~~~

We've got a basic sortable table with General Search Bar. If this is all you need, great! You're done! But if you want
to take advantage of some of the more advanced features, these next sections will focus on how to make these tools
more specific to your use case.

Adding More Filters
^^^^^^^^^^^^^^^^^^^^^

The default general filter is great, but maybe you want to search specific fields or other more complex parameters.
To do this we will need to modify our custom FilterSet. 
Let's start by adding a dropdown selection for "status" to our filter list:

.. code-block:: python
    :caption: myapp/filters.py
    :linenos:
    :emphasize-lines: 1, 2, 4, 9-12, 16

    import django_filters
    from django import forms

    from tom_common.htmx_table import HTMXTableFilterSet, htmx_attributes_instant
    from myapp.models import Observation

    class ObservationFilterSet(HTMXTableFilterSet):

        status = django_filters.ChoiceFilter(
            choices=Observation.OBSERVATION_STATUS_CHOICES,
            widget=forms.Select(attrs={htmx_attributes_instant})
        )

        class Meta:
            model = Observation
            fields = ['status']

NOTES:

- *Line 4:* We want to import our standard HTMX attributes that link this filter to the table. The TOMToolkit provides
  3 default options:

    - `htmx_attributes_instant` for triggering instant changes. Here we want the table to update immediately upon
      selection.
    - `htmx_attributes_onenter` for triggering table changes when the user hits enter. This is best used for complicated
      fields where a search doesn't make sense until all of the data is in.
    - `htmx_attributes_delayed` for triggering changes after a short (200ms) delay. We use this for character fields
      where a partial input is still viable. [3]_

- *Lines 9:* See the `django-filter documentation <https://django-filter.readthedocs.io/>`_ for more information. 
  Be sure to update the widget type on *line 11* (`forms.Select`) to one that makes sense with your filter. See 
  `Django Widgets <https://docs.djangoproject.com/en/6.0/ref/forms/widgets/#built-in-widgets>`_ for options.

- *Line 10:* This should be whatever choices are for the field. You can manually put a in a set of choices if you want:
  ``((1, 'Active'), (0, 'Inactive'))``

- *Line 11:* This is where we include the HTMX attributes for this field that allow them to update the table without
  reloading the whole page. 

- *Line 16:* Here we include the new field for this filter. All of the fields listed here will show up in a collapsed
  "Advanced" section by default.

You should now see a new "Advanced" collapsible menu appear under your general search bar containing all of your new
filters.

These simple filters are easy to include and update just by referencing a different field/filter type.
For example if we wanted to add a search field for the name as well, we would change the following:

.. code-block:: python
    :caption: myapp/filters.py
    :linenos:
    :emphasize-lines: 4, 14-17, 21

    import django_filters
    from django import forms

    from tom_common.htmx_table import HTMXTableFilterSet, htmx_attributes_instant, htmx_attributes_delayed
    from myapp.models import Observation

    class ObservationFilterSet(HTMXTableFilterSet):

        status = django_filters.ChoiceFilter(
            choices=Observation.OBSERVATION_STATUS_CHOICES,
            widget=forms.Select(attrs={**htmx_attributes_instant})
        )

        name = django_filters.CharFilter(
            lookup_expr='icontains',
            widget=forms.TextInput(attrs={**htmx_attributes_delayed, 'placeholder': 'Observation Name'})
        )

        class Meta:
            model = Observation
            fields = ['name', 'status']

NOTES:

- *Line 15:* This line will make it so the query returns observations where the name contains the input. By default,
  without this line, it must be an exact match.

- *Line 16:* We can add other attributes to the form field by simply appending them to the dictionary. Here we add
  placeholder text that will show up in the field before an actual search value is provided.

Now, both fields should show up in the advanced section and the resulting search will use BOTH filters, effectively 
providing an `AND` between both of them and the general search, only returning results that match all filters.

Advanced Filters
^^^^^^^^^^^^^^^^^^
Sometimes we want to do something a little more complicated than what the basic filters provide. For this we will need
to write our own functions. Let's make a filter for retrieving only recent observations. This will take the form of a
checkbox in the advanced section. Note: We've removed the other filters for simplicity, but the advanced filters will
work in concert with the others.

.. code-block:: python
    :caption: myapp/filters.py
    :linenos:
    :emphasize-lines: 11-26, 30

    from datetime import timedelta, datetime

    import django_filters
    from django import forms

    from tom_common.htmx_table import HTMXTableFilterSet, htmx_attributes_instant,
    from myapp.models import Observation

    class ObservationFilterSet(HTMXTableFilterSet):

        def get_recent(self, queryset, name, value):
            """
            Retrieve recent observations from within the last 24 hours

            :param queryset: The current filtered queryset. By filtering on this queryset,
                we respect the filters that precede this method in the filter chain.
            :param name: The name of the filter field calling this method (e.g. 'recent').
            :param value: The user's input from the form field.

            :Return queryset: Filtered queryset
            """
            if not value:
                return queryset  # early return
            
            yesterday = datetime.now() - timedelta(days = 1)
            return queryset.filter(date__gt=yesterday)

        recent = django_filters.BooleanFilter(
            label='New Observations',
            method = 'get_recent',
            help_text = 'Include only observations from within the last 24 hours',
            widget=forms.CheckboxInput(attrs={**htmx_attributes_instant})
        )

        class Meta:
            model = Observation
            fields = ['recent']

NOTES:

- *Lines 11-26:* We need to provide a function that performs our arbitrary query.

- *line 31:* We can add help text to our fields as well.

Including Model Properties In the Table Columns
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To include a model property (a model method tagged with the ``@property`` tag) we need to be a little cautious. 
Because the calculated properties are not present in the DB, and therefore are not as easy to sort on.

Unsortable Properties
=====================

If you don't want to sort on a property, just have it displayed in the Table, then it is fairly simple:

.. code-block:: python
    :caption: myapp/tables.py
    :linenos:
    :emphasize-lines: 6, 10

    from tom_common.htmx_table import HTMXTable  # HTMXTable is a django_tables2.Table subclass
    from myapp.models import Observation  # for example

    class ObservationTable(HTMXTable):

        example_property = tables.Column('example_property', orderable=False)

        class Meta(HTMXTable.Meta):
            model = Observation
            fields = ['selection', 'name', 'date', 'example_property', 'status']

NOTES:

- *Line 6:* We set `orderable = False` to prevent errors when trying to sort this as a DB field.

Sortable Properties
=====================

Things get a bit more complex when we try to sort by properties. See the `django_tables2 docs 
<https://django-tables2.readthedocs.io/en/latest/pages/ordering.html>`_ for more specifics, but basically we have to 
build our own sorting method using python and store the primary keys in the proper order. This is very expensive for 
large databases, and should only be done if your table won't ever hold too many objects.

.. code-block:: python
    :caption: myapp/tables.py
    :linenos:
    :emphasize-lines: 1, 8, 10-26

    from django.db.models import Case, When

    from tom_common.htmx_table import HTMXTable  # HTMXTable is a django_tables2.Table subclass
    from myapp.models import Observation  # for example

    class ObservationTable(HTMXTable):

        example_property = tables.Column('example_property', orderable=True)

        def order_example_property(self, queryset, is_descending):
            sorted_pks = [
                row.pk for row in sorted(
                    queryset,
                    key=lambda obj: obj.example_property or "" or 0,
                    reverse=is_descending,
                )
            ]

            # Use Case/When to preserve the Python-sorted order in the queryset
            # map the sorted PKs to the position in the enumeration
            preserved_order = Case(*[When(pk=pk, then=position) for position, pk in enumerate(sorted_pks)])

            # re-order the queryset by the python-sorted (the .filter is just for validation)
            sorted_queryset = queryset.filter(pk__in=sorted_pks).order_by(preserved_order)
            is_sorted = True
            return (sorted_queryset, is_sorted)

        class Meta(HTMXTable.Meta):
            model = Observation
            fields = ['selection', 'name', 'date', 'example_property', 'status']

NOTES:

- *Line 10 and 14:* Update these line with your property.

Formatting Our Form
^^^^^^^^^^^^^^^^^^^

So far we have relied on the default formatting with the general Search bar above our hidden advanced filters, and the
different advanced filters sorting themselves into rows and columns in the order they are entered into our
``Meta.fields``. We can customize this by overwriting our default form layout. Consult 
`django-crispy-forms <https://django-crispy-forms.readthedocs.io/en/latest/index.html>`_ for details on how to build a 
``Layout``. Here we will include most of the same infrastructure as before, but put each form field in its own row:

.. code-block:: python
    :caption: myapp/filters.py
    :linenos:
    :emphasize-lines: 1, 20-49

    from crispy_forms.layout import Layout, Div, Row, Column, HTML
    import django_filters
    from django import forms

    from tom_common.htmx_table import HTMXTableFilterSet, htmx_attributes_instant, htmx_attributes_delayed
    from myapp.models import Observation

    class ObservationFilterSet(HTMXTableFilterSet):

        status = django_filters.ChoiceFilter(
            choices=Observation.OBSERVATION_STATUS_CHOICES,
            widget=forms.Select(attrs={**htmx_attributes_instant})
        )

        name = django_filters.CharFilter(
            lookup_expr='icontains',
            widget=forms.TextInput(attrs={**htmx_attributes_delayed, 'placeholder': 'Observation Name'})
        )

        @property
        def form(self):
            if not hasattr(self, '_form'):
                self._form = super().form
                self._form.helper.layout = Layout(
                    Row(
                        Column('query', css_class='form-group col-md-3'),  # This is how we include the General Search
                    ),
                    HTML("""
                    <div class="row">
                        <div class="col-md-12 mb-2">
                            <a class="btn btn-link p-0" data-toggle="collapse"
                                href="#advancedFilters"
                                role="button" aria-expanded="false"
                                aria-controls="advancedFilters">Advanced &rsaquo;</a>
                        </div>
                    </div>
                    """),
                    Div(
                        Row(
                            Column('name', css_class='form-group col-md-3'),
                        ),
                        Row(
                            Column('status', css_class='form-group col-md-3'),
                        ),
                        css_class='collapse',
                        css_id='advancedFilters',
                    )
                )
            return self._form

        class Meta:
            model = Observation
            fields = ['name', 'status']

NOTES:

- *Lines 28-37, 45-46:* This handles the collapsible window.

- *lines 40 and 43:* Here we handle our fields, `name` and `status`.

See the example in `tom_targets/filters.py <https://github.com/TOMToolkit/tom_base/blob/dev/tom_targets/filters.py>`_.


Customizing General Search
^^^^^^^^^^^^^^^^^^^^^^^^^^
The default General search is quite broad and might even include fields that you don't want included in the table. 
There are several options for customizing this search functionality.

The ``HTMXTableFilterSet`` base class provides three ways to customize
the General Search behavior, in order of simplicity.

Override ``general_search()``
=============================

The most direct approach. Override the method in your ``HTMXTableFilterSet`` subclass:

.. code-block:: python
    :caption: myapp/filters.py
    :linenos:
    :emphasize-lines: 8-17

    from django.db.models import Q

    from tom_common.htmx_table import HTMXTableFilterSet
    from myapp.models import Observation

    class ObservationFilterSet(HTMXTableFilterSet):

        def general_search(self, queryset, name, value):
        """This general_search method searches the ``name`` and ``observer.username``
        Model fields for the text in the ``query`` CharField of the ``FilterSet``.
        """
            if not value:
                return queryset
            return queryset.filter(
                Q(name__icontains=value) |
                Q(observer__username__icontains=value)
            )

        class Meta:
            model = Observation
            fields = []


Settings-Based Override (``GENERAL_SEARCH_FUNCTIONS``)
=======================================================

Register a standalone function in ``settings.py`` without subclassing
anything. This is useful in a ``custom_code`` app where you want to
change the search behavior for an existing TOM Toolkit model.

.. code-block:: python
    :caption: settings.py

    GENERAL_SEARCH_FUNCTIONS = {
        'tom_targets.Target': 'custom_code.search.my_target_search',
    }

.. code-block:: python
    :caption: custom_code/search.py
    :linenos:

    from django.db.models import Q

    def my_target_search(queryset, name, value):
        """
            Change the existing general search function on the Target List page to include aliases as well as 
            target names.
        """
        if not value:
            return queryset
        return queryset.filter(
            Q(name__icontains=value) |
            Q(aliases__name__icontains=value)
        ).distinct()

The key to the `GENERAL_SEARCH_FUNCTIONS` dictionary is ``'app_label.ModelName'`` (e.g. ``'tom_targets.Target'``)
and the value is a dotted path to a callable with the signature
``(queryset, name, value) -> QuerySet``. If a matching entry exists in
``GENERAL_SEARCH_FUNCTIONS``, it takes priority over the FilterSet's
``general_search()`` method.


Override ``get_general_search_function()``
==========================================

For full control, override ``get_general_search_function()`` in a
FilterSet subclass. This lets you return any callable based on runtime
conditions.

.. code-block:: python
    :caption: custom_code/filters.py
    :linenos:

    from tom_targets.filters import TargetFilterSet
    from django.db.models import Q

    class CustomTargetFilterSet(TargetFilterSet):
        """Override the general search without changing the View."""

        def get_general_search_function(self):
            return self.my_custom_search

        def my_custom_search(self, queryset, name, value):
            """
                Change the existing general search function on the Target List page to include aliases as well as 
                target names.
            """
            if not value:
                return queryset
            return queryset.filter(
                Q(name__icontains=value) |
                Q(aliases__name__icontains=value)
            ).distinct()

Then point your view at the custom FilterSet:

.. code-block:: python
    :caption: custom_code/views.py
    :linenos:

    from tom_targets.views import TargetListView
    from custom_code.filters import CustomTargetFilterSet

    class CustomTargetListView(TargetListView):
        filterset_class = CustomTargetFilterSet


General Search Examples
=======================
Note: These examples are given in the context of modifying the general search functionality, but could just as easily
be used on their own to define one of your Advanced Filters described above.

**Multi-field search**
++++++++++++++++++++++
Using Django's ``Q`` objects
`(docs) <https://docs.djangoproject.com/en/5.2/topics/db/queries/#complex-lookups-with-q-objects>`_:

.. code-block:: python

    def general_search(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(name__icontains=value) |
            Q(description__icontains=value) |
            Q(observer__username__icontains=value)
        )

**Type-based search**
+++++++++++++++++++++
Detect numeric input and search coordinate fields:

.. code-block:: python

    from decimal import Decimal, InvalidOperation

    def general_search(self, queryset, name, value):
        if not value:
            return queryset

        if value.replace(".", "", 1).replace("-", "", 1).isdigit():
            try:
                numeric_value = Decimal(value)
                return queryset.filter(
                    Q(ra__icontains=numeric_value) |
                    Q(dec__icontains=numeric_value)
                )
            except (InvalidOperation, ValueError):
                pass

        return queryset.filter(Q(name__icontains=value))

**Comma-separated search**
++++++++++++++++++++++++++
With OR logic:

.. code-block:: python

    def general_search(self, queryset, name, value):
        if not value:
            return queryset

        # extract search terms from the input value
        terms = [term.strip() for term in value.split(',')]
        q_objects = Q()
        for term in terms:
            q_objects |= (
                Q(name__icontains=term) |
                Q(aliases__name__icontains=term)
            )
        return queryset.filter(q_objects).distinct()

Overwriting the Table Partial
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The base class provides a default partial template at
``tom_common/partials/htmx_table_partial.html`` that renders the table
and shows a generic empty-state (no data) message.

If you need a custom partial (e.g. model-specific empty-state messages),
create one and set ``partial_template_name`` on your Table subclass:

.. code-block:: python
    :caption: myapp/tables.py
    :linenos:
    :emphasize-lines: 7

    from tom_common.htmx_table import HTMXTable
    from myapp.models import Observation

    class ObservationTable(HTMXTable):

        # specify the path to your custom partial for you table
        partial_template_name = "myapp/partials/observation_table_partial.ht

        class Meta(HTMXTable.Meta):
            model = Observation
            fields = ['name', 'date', 'status']

.. code-block:: html+django
    :caption: myapp/templates/myapp/partials/observation_table_partial.html
    :linenos:

    {% load render_table from django_tables2 %}

    {% render_table table %}

    {% if not table.data %}
        <div class="alert alert-info mt-3">
            {% if empty_database %}
                No observations in the database yet.
            {% else %}
                No observations match those filters.
            {% endif %}
        </div>
    {% endif %}

See the reference implementation in
``tom_targets/templates/tom_targets/partials/target_table_partial.html``.

Note: ``tom_common/partials/htmx_table_partial.html`` contains the javascript necessary to make the check box selection
work properly. If you intend to include checkboxes, you will want to copy this script into your partial as well.

Best Practices
^^^^^^^^^^^^^^^
- ``FilterSet``s pass a queryset from Filter to Filter. So,
  always return the queryset unchanged when ``value`` is empty
- Use ``.distinct()`` when searching across related model fields


Troubleshooting
~~~~~~~~~~~~~~~~

**HTMX returns the full page instead of the partial**
  Check that ``django_htmx.middleware.HtmxMiddleware`` is in your
  ``MIDDLEWARE`` setting and that your view includes
  ``HTMXTableViewMixin``.

**Filters are lost when sorting or paginating**
  Ensure your filter form has ``id="filter-form"`` (matching the
  ``"hx-include": "#filter-form"`` in ``HTMXTable.Meta.attrs``).

**Progress indicator does not appear**
  Verify that ``<div class="progress"><div class="indeterminate"></div></div>``
  is present in your main page template and that ``hx-indicator=".progress"``
  is set on the interactive elements.

**General search is not filtering results**
  Check that your FilterSet subclasses ``HTMXTableFilterSet`` and that
  ``general_search()`` returns a filtered queryset (not ``None``).


Where to Find More Information
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- `django-tables2 documentation <https://django-tables2.readthedocs.io/>`_
- `HTMX documentation <https://htmx.org/docs/>`_
- `django-filter documentation <https://django-filter.readthedocs.io/>`_
- `django-htmx documentation <https://django-htmx.readthedocs.io/>`_


.. rubric:: Footnotes

.. [1] ``HTMXTable`` inherits from ``django_tables2.Table`` and sets
   ``Meta.template_name`` to a shared Bootstrap/HTMX template that adds
   HTMX attributes to column headers (for sorting) and pagination
   controls. It also sets ``Meta.attrs`` with ``hx-include``,
   ``hx-target``, ``hx-swap``, and ``hx-boost``.

.. [2] ``hx-boost="true"`` on the ``<table>`` element (set by
   ``HTMXTable.Meta.attrs``) intercepts the ``<a>`` tags that
   django-tables2 generates for sorting and pagination, converting them
   into HTMX AJAX requests. Links to detail pages use
   ``hx-boost="false"`` to opt out and trigger normal navigation.

.. [3] The `htmx_attributes_delayed` dicitonary includes a ``delay:200ms`` modifier that acts as
   a debounce -- the request is only sent after the user stops typing for
   200ms. Combined with ``hx-sync="this:replace"``, any in-flight request
   is cancelled and replaced by the latest one, preventing race
   conditions.

.. [4] ``HTMXTableViewMixin`` checks ``self.request.htmx`` (provided by
   ``django_htmx.middleware.HtmxMiddleware``). When an HTMX request
   arrives, only the partial template is returned; otherwise the full page
   template is used. The ``record_count`` context variable comes from
   ``context['paginator'].count``.

.. [5] Without ``hx-include``, sorting and pagination requests would not
   carry the current filter parameters, causing the table to reset its
   filters on every sort or page change.

.. |image0| image:: /_static/htmx_tables_doc/sortable_table_with_general_search.png