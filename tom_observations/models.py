from django.contrib.auth.models import User
from django.db import models

from tom_targets.models import Target
from tom_observations.facility import get_service_class
from tom_common.hooks import run_hook


class ObservationRecord(models.Model):
    """
    Class representing an observation in a TOM.

    A ObservationRecord corresponds with any set of related exposures at a facility, and is associated with a single
    target.

    :param target: The ``Target`` with which this object is associated.
    :type target: Target

    :param facility: The facility at which this observation is taken. Should be the name specified in the corresponding
        TOM facility module, if one exists.
    :type facility: str

    :param parameters: The set of parameters used in the API request made to create the observation
    :type parameters: dict

    :param status: The current status of the observation. Should be a valid status in the corresponding TOM facility
        module, if one exists.
    :type status: str

    :param scheduled_start: The time at which the observation is scheduled to begin, according to the facility.
    :type scheduled_start: datetime

    :param scheduled_end: The time at which the observation is scheduled to end, according to the facility.
    :type scheduled_end: datetime

    :param created: The time at which this object was created.
    :type created: datetime

    :param modified: The time at which this object was last updated.
    :type modified: datetime
    """
    target = models.ForeignKey(Target, on_delete=models.CASCADE)
    user = models.ForeignKey(User, null=True, default=None, on_delete=models.DO_NOTHING)
    facility = models.CharField(max_length=50)
    parameters = models.JSONField()
    observation_id = models.CharField(max_length=255)
    status = models.CharField(max_length=200)
    scheduled_start = models.DateTimeField(null=True)
    scheduled_end = models.DateTimeField(null=True)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created',)

    def save(self, *args, **kwargs):
        if self.id:
            presave_data = ObservationRecord.objects.get(pk=self.id)
            super().save(*args, **kwargs)
            if self.status != presave_data.status:
                run_hook('observation_change_state', self, presave_data.status)
        else:
            super().save(*args, **kwargs)
            run_hook('observation_change_state', self, None)

    @property
    def terminal(self):
        facility = get_service_class(self.facility)
        return self.status in facility().get_terminal_observing_states()

    @property
    def failed(self):
        facility = get_service_class(self.facility)
        return self.status in facility().get_failed_observing_states()

    @property
    def url(self):
        facility = get_service_class(self.facility)
        return facility().get_observation_url(self.observation_id)

    def update_status(self):
        facility = get_service_class(self.facility)
        facility().update_observation_status(self.id)

    def save_data(self):
        facility = get_service_class(self.facility)
        facility().save_data_products(self)

    def __str__(self):
        return '{0} @ {1}'.format(self.target, self.facility)


class ObservationGroup(models.Model):
    """
    Class representing a logical group of observations.

    :param name: The name of the grouping.
    :type name: str

    :param observation_records: Set of ``ObservationRecord`` objects associated with this ``ObservationGroup``

    :param created: The time at which this ``ObservationGroup`` was created.
    :type created: datetime

    :param modified: The time at which this ``ObservationGroup`` was modified.
    :type modified: datetime
    """
    name = models.CharField(max_length=50)
    observation_records = models.ManyToManyField(ObservationRecord)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created', 'name',)

    def __str__(self):
        return self.name


class DynamicCadence(models.Model):
    """
    Class representing a dynamic cadence--that is, a cadence that follows a pattern but modifies its behavior
    depending on the result of prior observations.

    :param observation_group: The ``ObservationGroup`` containing the observations that were created by this cadence.
    :type observation_group: ``ObservationGroup``

    :param cadence_strategy: The name of the cadence strategy this cadence is using.
    :type cadence_strategy: str

    :param cadence_parameters: The parameters for this cadence, e.g. cadence period
    :type cadence_parameters: JSON

    :param active: Whether or not this cadence should continue to submit observations
    :type active: boolean

    :param created: The time at which this ``DynamicCadence`` was created.
    :type created: datetime

    :param modified: The time at which this ``DynamicCadence`` was modified.
    :type modified: datetime
    """
    observation_group = models.ForeignKey(ObservationGroup, null=False, default=None, on_delete=models.CASCADE)
    cadence_strategy = models.CharField(max_length=100, blank=False, default=None,
                                        verbose_name='Cadence strategy used for this DynamicCadence')
    cadence_parameters = models.JSONField(blank=False, null=False, verbose_name='Cadence-specific parameters')
    active = models.BooleanField(verbose_name='Active',
                                 help_text='''Whether or not this DynamicCadence should
                                           continue to submit observations.''')
    created = models.DateTimeField(auto_now_add=True, help_text='The time which this DynamicCadence was created.')
    modified = models.DateTimeField(auto_now=True, help_text='The time which this DynamicCadence was modified.')

    def __str__(self):
        return f'{self.cadence_strategy} with parameters {self.cadence_parameters}'


class ObservationTemplate(models.Model):
    """
    Class representing an observation template.

    :param name: The name of the ``ObservationTemplate``
    :type name: str

    :param facility: The module-specified facility name for which the template is valid
    :type facility: str

    :param parameters: Observing parameters
    :type parameters: dict

    :param created: The time at which this ``ObservationTemplate`` was created.
    :type created: datetime

    :param modified: The time at which this ``ObservationTemplate`` was modified.
    :type modified: datetime
    """
    name = models.CharField(max_length=200)
    facility = models.CharField(max_length=50)
    parameters = models.JSONField()
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
