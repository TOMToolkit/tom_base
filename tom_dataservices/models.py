from django.db import models


class DataServiceQuery(models.Model):
    """
    Class representing a query to a broker in a TOM

    :param name: The user-given name of this query.
    :type name: str

    :param data_service: The name of the data service--this should come directly from the ``name`` attribute of
        the DataService class representing the data service.
    :type data_service: str

    :param parameters: Parameters for this ``BrokerQuery``, stored as a JSON string.
    :type parameters: dict

    :param created: The time at which this ``BrokerQuery`` was created in the TOM database.
    :type created: datetime

    :param modified: The time at which this ``BrokerQuery`` was changed in the TOM database.
    :type modified: datetime

    :param last_run: The time at which this ``BrokerQuery`` was last run against its corresponding broker.
    :type last_run: datetime
    """
    name = models.CharField(max_length=500)
    data_service = models.CharField(max_length=50)
    parameters = models.JSONField()
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)
    last_run = models.DateTimeField(blank=True, null=True, default=None)

    def __str__(self):
        return self.name
