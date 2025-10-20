from django.db import models


class DataServiceQuery(models.Model):
    """
    Class representing a query to a Data Service in a TOM
    Fields:
        name: The user-given name of this query.
        data_service: The name of the data service--this should come directly from the ``name`` attribute of
           the DataService class representing the data service.
        parameters: Parameters for this ``DataServiceQuery``, stored as a JSON string.
        created: The time at which this ``DataServiceQuery`` was created in the TOM database.
        modified: The time at which this ``DataServiceQuery`` was changed in the TOM database.
        last_run: The time at which this ``DataServiceQuery`` was last run against its corresponding broker.
    """
    name = models.CharField(max_length=500)
    data_service = models.CharField(max_length=50)
    parameters = models.JSONField()
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)
    last_run = models.DateTimeField(blank=True, null=True, default=None)

    def __str__(self):
        return self.name
