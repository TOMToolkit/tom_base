from django.db import models


class BrokerQuery(models.Model):
    """
    Class representing a query to a broker in a TOM

    :param name: The user-given name of this query.
    :type name: str

    :param broker: The name of the broker--this should come directly from the ``name`` attribute of the broker class
                   representing the broker.
    :type broker: str

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
    broker = models.CharField(max_length=50)
    parameters = models.JSONField()
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)
    last_run = models.DateTimeField(blank=True, null=True, default=None)

    def __str__(self):
        return self.name


class AlertStreamMessage(models.Model):
    """
    Class representing a streaming message containing data sent/received either over Kafka or to/from another TOM
    :param topic: The destination or source of sharing for the message.
    :type topic: str

    :param message_id: An external message identifier that can be used to locate the message within the given topic.
    :type message_id: str

    :param date_shared: The date on which the message is shared. (Date created by default.)
    :type date_shared: datetime

    :param exchange_status: Whether this message was sent or received.
    :type exchange_status: str
    """

    EXCHANGE_STATUS_CHOICES = (
        ('published', 'Published'),
        ('ingested', 'Ingested')
    )

    topic = models.CharField(
        max_length=500,
        verbose_name='Message Topic',
        help_text='The destination or source of sharing for the message.'
    )
    message_id = models.CharField(
        max_length=50,
        null=True,
        verbose_name='Message ID',
        help_text='An external message identifier that can be used to locate the message within the given topic.'
    )
    date_shared = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Date Shared',
        help_text='The date on which the message is shared. (Date created by default.)'
    )
    exchange_status = models.CharField(
        max_length=10,
        verbose_name='Exchange Status',
        choices=EXCHANGE_STATUS_CHOICES,
        help_text='Whether this message was sent or received.'
    )

    def __str__(self):
        return f'Message {self.message_id} on {self.topic}.'
