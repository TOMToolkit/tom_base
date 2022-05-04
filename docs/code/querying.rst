Querying on related objects
===========================

An aspect of programmatic TOM Toolkit access that is often desired is
filtering by related objects. While this is extensively documented in
the Django documentation, it’s certainly helpful to see a couple of
examples in action.

Identifying Targets by TargetExtra values
-----------------------------------------

There may be times that you want to find Targets by specific parameters.
It’s fairly trivial to, for example, find a set of Targets by RA:

.. code:: python

   >>> from tom_targets.models import Target
   >>> Target.objects.filter(ra=356.58)

However, this isn’t terribly helpful, as you need to know the exact
value of RA that you’re looking for to find your Target. Fortunately,
the Django QuerySet API offers a number of additional functions,
including `Field
lookups <https://docs.djangoproject.com/en/3.0/ref/models/querysets/#field-lookups>`__:

.. code:: python

   >>> Target.objects.filter(ra__lte=357, ra__gte=356)

The above query will look for Targets with RAs between 356 and 357.
Field lookups can be used for more granular queries, and it’s encouraged
to reference the Django Queryset API Docs to familiarize yourself.

While the previous query is very useful for searching in a range, what
about when you aren’t filtering on base Target fields? A common use case
of the TOM ``TargetExtra`` model is for fields that aren’t on Targets by
default. Let’s take the example of supernovae. Let’s say that you have a
TOM for tracking supernovae, and you’ve added redshift as a TargetExtra.
How does one find Targets with the appropriate redshift?

.. code:: python

   >>> Target.objects.filter(targetextra__key='redshift', targetextra__value__gt=0.5)

That query will first find Targets with a TargetExtra of ``redshift``,
and will filter those particular TargetExtras for a value of greater
than 0.5.

Adding Targets to Groups programmatically
-----------------------------------------

Another operation that one might desire to do programmatically is adding
Targets to Groups. This can be done in a relatively straightforward
manner as well:

.. code:: python

   from tom_targets.models import TargetList
   >>> Target.objects.all()
   <QuerySet [<Target: M51>, <Target: M31>]>
   >>> TargetList.objects.all()
   <QuerySet []>
   >>> tl = TargetList(name='My Target List')
   >>> tl.save()
   >>> tl.refresh_from_db()
   >>> tl.id
   1
   >>> tl.targets.all()
   <QuerySet []>
   >>> tl.targets.add(Target.objects.first())
   >>> tl.targets.all()
   <QuerySet [<Target: M51>]>

Related objects can be obtained in either direction:

.. code:: python

   >>> t.targetlist_set.all()
   <QuerySet [<TargetList: My Target List>]>
   >>> tl.targets.all()
   <QuerySet [<Target: M51>]>
