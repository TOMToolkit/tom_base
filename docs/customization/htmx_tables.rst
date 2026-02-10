Building Interactive HTMX Tables
-----------------------------------

TOM Toolkit provides base classes for building interactive data tables with
filtering, sorting, and pagination that avoid full-page reloads using
`HTMX <https://htmx.org/>`_.

Three model-independent bases classes in ``tom_common.htmx_table`` handle
common concerns so that creating a new HTMX-driven table for any model is largely
a configuration task. [1]_. The provided classes are:

 - ``HTMXTable`` - This class extends ``django_tables2.Table``
   to add HTMX attributes to certain HTML elements, handles checkboxes, etc.
   Your subclass will define your table, specifying the Model supplying data to your
   table and the fields that will be displayed.

 - ``HTMXTableFilterSet`` - Your subclass will define data filters and add HTMX
   elements to update your table as the filters change.

 - ``HTMXTableViewMixin`` - This mix-in class must be added to your ListView subclasses
   that present their data in ``HTMXTable`` subclasses. It recognizes AJAX (HTMX) requests
   and adds pagination data to your ListView's context.

Creating a Table for Your Model
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This section walks through the three pieces you need: a Table class, a
FilterSet class, and a View. The `Target list page <https://tom-demo.lco.global/targets/>`_
provides an example implementation for each step.


Step 1: Define the Table
^^^^^^^^^^^^^^^^^^^^^^^^^

A ``tables.py`` module in your app or ``custom_code`` is good place to
define your ``HTMXTable``.
Subclass ``HTMXTable`` in ``tables.py``. The base class
provides the Bootstrap/HTMX template, row-selection checkboxes, and
all the ``Meta.attrs`` needed for sorting and pagination to work via
HTMX. [2]_ Your subclass ``Meta.attrs`` must specify the  Model and Fields
to be displayed.

.. code-block:: python

    # myapp/tables.py
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

- Include ``'selection'`` in ``fields`` to enable row-selection checkboxes.

- Use ``linkify=True`` on a column to turn cell values into links to the
  object's detail page (``get_absolute_url()``).

- The ``hx-boost="false"``
  attribute ensures that clicking the link triggers a normal page navigation
  (to the object's detail page) rather than being intercepted by HTMX. [3]_

See the example in `tom_targets/tables.py <https://github.com/TOMToolkit/tom_base/tree/dev/tom_targets>`_.


Step 2: Create the FilterSet
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
This section assumes some familiarity with the `django-filter <https://django-filter.readthedocs.io/en/stable/index.html>`_
and `django-crispy-forms <https://django-crispy-forms.readthedocs.io/en/latest/index.html>`_ packages.

Subclass ``HTMXTableFilterSet`` from ``tom_common.htmx_table``. The base
class provides a General Search text field (``query``) with debounced
HTMX attributes already configured. Override ``general_search()`` with
your model-specific search logic, and add any additional filters your
table needs.

.. code-block:: python

    # myapp/filters.py
    import django_filters
    from django import forms
    from django.db.models import Q

    from crispy_forms.helper import FormHelper
    from crispy_forms.layout import Layout, Row, Column, Div, HTML

    from tom_common.htmx_table import HTMXTableFilterSet
    from myapp.models import Observation

    class ObservationFilterSet(HTMXTableFilterSet):

        def general_search(self, queryset, name, value):
            """Search observations by name."""
            if not value:
                return queryset
            return queryset.filter(Q(name__icontains=value))

        status = django_filters.ChoiceFilter(
            choices=[('active', 'Active'), ('completed', 'Completed')],
            widget=forms.Select(attrs={
                'hx-get': "",
                'hx-trigger': "change",
                'hx-target': "div.table-container",
                'hx-swap': "innerHTML",
                'hx-indicator': ".progress",
                'hx-include': "closest form",
            })
        )

        @property
        def form(self):
            if not hasattr(self, '_form'):
                self._form = super().form
                self._form.helper = FormHelper()
                self._form.helper.form_tag = False
                self._form.helper.disable_csrf = True
                self._form.helper.form_show_labels = True
                self._form.helper.layout = Layout(
                    Row(
                        Column('query', css_class='form-group col-md-3'),
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
                            Column('status', css_class='form-group col-md-3'),
                        ),
                        css_class='collapse',
                        css_id='advancedFilters',
                    )
                )
            return self._form

        class Meta:
            model = Observation
            fields = ['status']

NOTES:

- The General Search text field fires after a short (debounced) pause in typing.

- Dropdown filters use ``hx-trigger="change"`` for immediate
  response on selection. [4]_

- The ``form`` property override configures ``crispy-forms`` with
  ``form_tag=False`` because the main page template provides the
  ``<form>`` element.

- The ``query`` field goes in the primary row; extra
  filters go inside a collapsible "Advanced" section.


See the example in `tom_targets/filters.py <https://github.com/TOMToolkit/tom_base/blob/dev/tom_targets/filters.py>`_.


Step 3: Update the View
^^^^^^^^^^^^^^^^^^^^^^^^^

Add ``HTMXTableViewMixin`` to your existing List (or Filter) view. The mixin extends
``django_tables2.SingleTableMixin`` and handles HTMX request detection
and template selection. It also adds ``record_count`` and
``empty_database`` to the template context. [5]_

.. code-block:: python

    # myapp/views.py
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

See the example in `tom_targets/views.py <https://github.com/TOMToolkit/tom_base/blob/dev/tom_targets/views.py>`_.

Step 4: Set Up the Templates
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You need two templates: a main page template and a partial template.
The bootstrap HTMX template (for sorting and pagination) and a default
partial template are provided by the base classes.

**a) Main page template**

The main page template wraps the filter form, progress indicator, and
table container.

.. code-block:: html+django

    {# myapp/templates/myapp/observation_list.html #}
    {% extends 'tom_common/base.html' %}
    {% load render_table from django_tables2 %}
    {% load crispy_forms_tags %}

    {% block title %}Observations{% endblock %}

    {% block content %}
    <div class="row">
      <div class="col-md-12">
        <h2>{{ record_count }} Observation{{ record_count|pluralize }}</h2>
        <hr>

        {# Filter form -- id must match hx-include in the Table's Meta.attrs #}
        <form id="filter-form" class="mb-3"
              hx-get="{% url 'myapp:list' %}"
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
            {% include "myapp/partials/observation_table_partial.html" %}
        </div>
      </div>
    </div>
    {% endblock content %}

NOTES:

- The ``id="filter-form"`` must match the ``"hx-include": "#filter-form"``
  in ``HTMXTable.Meta.attrs`` so that filter values are preserved during
  sorting and pagination. [6]_

See the reference implementation in
``tom_targets/templates/tom_targets/target_list.html``.

**b) Partial template (optional)**

The base class provides a default partial template at
``tom_common/partials/htmx_table_partial.html`` that renders the table
and shows a generic empty-state (no data) message.

If you need a custom partial (e.g. model-specific empty-state messages),
create one and set ``partial_template_name`` on your Table subclass:

.. code-block:: python

    class ObservationTable(HTMXTable):
        # ...
        # specify the path to your custom partial for you table
        partial_template_name = "myapp/partials/observation_table_partial.html"

.. code-block:: html+django

    {# myapp/templates/myapp/partials/observation_table_partial.html #}
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


Customizing General Search
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``HTMXTableFilterSet`` base class provides three ways to customize
the General Search behavior, in order of simplicity.

Override ``general_search()``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The most direct approach. Override the method in your ``HTMXTableFilterSet``
subclass:

.. code-block:: python

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
            fields = ['status']


Settings-Based Override (``GENERAL_SEARCH_FUNCTIONS``)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Register a standalone function in ``settings.py`` without subclassing
anything. This is useful in a ``custom_code`` app where you want to
change the search behavior for an existing TOM Toolkit model.

.. code-block:: python

    # settings.py
    GENERAL_SEARCH_FUNCTIONS = {
        'tom_targets.Target': 'custom_code.search.my_target_search',
    }

.. code-block:: python

    # custom_code/search.py
    from django.db.models import Q

    def my_target_search(queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(name__icontains=value) |
            Q(aliases__name__icontains=value)
        ).distinct()

The key is ``'app_label.ModelName'`` (e.g. ``'tom_targets.Target'``)
and the value is a dotted path to a callable with the signature
``(queryset, name, value) -> QuerySet``. If a matching entry exists in
``GENERAL_SEARCH_FUNCTIONS``, it takes priority over the FilterSet's
``general_search()`` method.


Override ``get_general_search_function()``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

For full control, override ``get_general_search_function()`` in a
FilterSet subclass. This lets you return any callable based on runtime
conditions.

.. code-block:: python

    # custom_code/filters.py
    from tom_targets.filters import TargetFilterSet
    from django.db.models import Q

    class CustomTargetFilterSet(TargetFilterSet):
        """Override the general search without changing the View."""

        def get_general_search_function(self):
            return self.my_custom_search

        def my_custom_search(self, queryset, name, value):
            if not value:
                return queryset
            return queryset.filter(
                Q(name__icontains=value) |
                Q(aliases__name__icontains=value)
            ).distinct()

Then point your view at the custom FilterSet:

.. code-block:: python

    # custom_code/views.py
    from tom_targets.views import TargetListView
    from custom_code.filters import CustomTargetFilterSet

    class CustomTargetListView(TargetListView):
        filterset_class = CustomTargetFilterSet


General Search Examples
^^^^^^^^^^^^^^^^^^^^^^^^

**Multi-field search** using Django's ``Q`` objects
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

**Type-based search** -- detect numeric input and search coordinate
fields:

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

**Comma-separated search** with OR logic:

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

.. [1] The three base classes are ``HTMXTable``, ``HTMXTableFilterSet``,
   and ``HTMXTableViewMixin``, all in ``tom_common.htmx_table``. The
   underlying libraries (django-tables2, django-filter, django-htmx) are
   already included in TOM Toolkit.

.. [2] ``HTMXTable`` inherits from ``django_tables2.Table`` and sets
   ``Meta.template_name`` to a shared Bootstrap/HTMX template that adds
   HTMX attributes to column headers (for sorting) and pagination
   controls. It also sets ``Meta.attrs`` with ``hx-include``,
   ``hx-target``, ``hx-swap``, and ``hx-boost``.

.. [3] ``hx-boost="true"`` on the ``<table>`` element (set by
   ``HTMXTable.Meta.attrs``) intercepts the ``<a>`` tags that
   django-tables2 generates for sorting and pagination, converting them
   into HTMX AJAX requests. Links to detail pages use
   ``hx-boost="false"`` to opt out and trigger normal navigation.

.. [4] The ``delay:200ms`` modifier on the General Search field acts as
   a debounce -- the request is only sent after the user stops typing for
   200ms. Combined with ``hx-sync="this:replace"``, any in-flight request
   is cancelled and replaced by the latest one, preventing race
   conditions.

.. [5] ``HTMXTableViewMixin`` extends ``django_tables2.SingleTableMixin``
   and checks ``self.request.htmx`` (provided by
   ``django_htmx.middleware.HtmxMiddleware``). When an HTMX request
   arrives, only the partial template is returned; otherwise the full page
   template is used. The ``record_count`` context variable comes from
   ``context['paginator'].count``.

.. [6] Without ``hx-include``, sorting and pagination requests would not
   carry the current filter parameters, causing the table to reset its
   filters on every sort or page change.
