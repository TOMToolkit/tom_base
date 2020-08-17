from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from dateutil.parser import parse
from importlib import import_module
import json

from crispy_forms.layout import Column, Div, HTML, Layout, Row
from django import forms
from django.conf import settings

from tom_observations.facility import get_service_class
from tom_observations.models import ObservationRecord


DEFAULT_CADENCE_STRATEGIES = [
    'tom_observations.cadence.RetryFailedObservationsStrategy',
    'tom_observations.cadence.ResumeCadenceAfterFailureStrategy'
]


def get_cadence_strategies():
    try:
        TOM_CADENCE_STRATEGIES = settings.TOM_CADENCE_STRATEGIES
    except AttributeError:
        TOM_CADENCE_STRATEGIES = DEFAULT_CADENCE_STRATEGIES

    cadence_choices = {}
    for cadence in TOM_CADENCE_STRATEGIES:
        mod_name, class_name = cadence.rsplit('.', 1)
        try:
            mod = import_module(mod_name)
            clazz = getattr(mod, class_name)
        except (ImportError, AttributeError):
            raise ImportError(f'Could not import {cadence}. Did you provide the correct path?')
        cadence_choices[class_name] = clazz
    return cadence_choices


def get_cadence_strategy(name):
    available_classes = get_cadence_strategies()
    try:
        return available_classes[name]
    except KeyError:
        raise ImportError('Could not a find a facility with that name. Did you add it to TOM_FACILITY_CLASSES?')


class CadenceStrategy(ABC):
    """
    The CadenceStrategy interface provides the methods necessary to implement a custom cadence strategy. All
    CadenceStrategies should inherit from this base class.

    In order to make use of a custom CadenceStrategy, add the path to ``TOM_CADENCE_STRATEGIES`` in your
    ``settings.py``.
    """
    def __init__(self, observation_group, *args, **kwargs):
        self.cadence_strategy = type(self).__name__
        self.observation_group = observation_group

    @abstractmethod
    def run(self):
        pass


class RetryFailedObservationsStrategy(CadenceStrategy):
    """
    The RetryFailedObservationsStrategy immediately re-submits all observations within an observation group a certain
    number of hours later, as specified by ``advance_window_hours``.
    """
    name = 'Retry Failed Observations'
    description = """This strategy immediately re-submits a cadenced observation without amending any other part of the
                     cadence."""

    def __init__(self, observation_group, advance_window_hours, *args, **kwargs):
        self.advance_window_hours = advance_window_hours
        super().__init__(observation_group, *args, **kwargs)

    def run(self):
        failed_observations = [obsr for obsr in self.observation_group.observation_records.all() if obsr.failed]
        new_observations = []
        for obs in failed_observations:
            observation_payload = obs.parameters_as_dict
            facility = get_service_class(obs.facility)()
            start_keyword, end_keyword = facility.get_start_end_keywords()
            observation_payload = self.advance_window(
                observation_payload, start_keyword=start_keyword, end_keyword=end_keyword
            )
            obs_type = obs.parameters_as_dict.get('observation_type', None)
            form = facility.get_form(obs_type)(observation_payload)
            form.is_valid()
            observation_ids = facility.submit_observation(form.observation_payload())

            for observation_id in observation_ids:
                # Create Observation record
                record = ObservationRecord.objects.create(
                    target=obs.target,
                    facility=facility.name,
                    parameters=json.dumps(observation_payload),
                    observation_id=observation_id
                )
                self.observation_group.observation_records.add(record)
                self.observation_group.save()
                new_observations.append(record)

        return new_observations

    def advance_window(self, observation_payload, start_keyword='start', end_keyword='end'):
        new_start = parse(observation_payload[start_keyword]) + timedelta(hours=self.advance_window_hours)
        new_end = parse(observation_payload[end_keyword]) + timedelta(hours=self.advance_window_hours)
        observation_payload[start_keyword] = new_start.isoformat()
        observation_payload[end_keyword] = new_end.isoformat()

        return observation_payload


class ResumeCadenceAfterFailureStrategy(CadenceStrategy):
    """The ResumeCadenceAfterFailureStrategy chooses when to submit the next observation based on the success of the
    previous observation. If the observation is successful, it submits a new one on the same cadence--that is, if the
    cadence is every three days, it will submit the next observation three days in the future. If the observations
    fails, it will submit the next observation immediately, and follow the same decision tree based on the success
    of the subsequent observation."""

    name = 'Resume Cadence After Failure'
    description = """This strategy schedules one observation in the cadence at a time. If the observation fails, it
                     re-submits the observation until it succeeds. If it succeeds, it submits the next observation on
                     the same cadence."""

    def __init__(self, observation_group, advance_window_hours, *args, **kwargs):
        self.advance_window_hours = advance_window_hours
        super().__init__(observation_group, *args, **kwargs)

    def run(self):
        last_obs = self.observation_group.observation_records.order_by('-created').first()
        facility = get_service_class(last_obs.facility)()
        facility.update_observation_status(last_obs.observation_id)
        last_obs.refresh_from_db()
        start_keyword, end_keyword = facility.get_start_end_keywords()
        observation_payload = last_obs.parameters_as_dict
        new_observations = []
        if not last_obs.terminal:
            return
        elif last_obs.failed:
            # Submit next observation to be taken as soon as possible
            window_length = parse(observation_payload[end_keyword]) - parse(observation_payload[start_keyword])
            observation_payload[start_keyword] = datetime.now().isoformat()
            observation_payload[end_keyword] = (parse(observation_payload[start_keyword]) + window_length).isoformat()
        else:
            # Advance window normally according to cadence parameters
            observation_payload = self.advance_window(
                observation_payload, start_keyword=start_keyword, end_keyword=end_keyword
            )

        obs_type = last_obs.parameters_as_dict.get('observation_type')
        form = facility.get_form(obs_type)(observation_payload)
        form.is_valid()
        observation_ids = facility.submit_observation(form.observation_payload())

        for observation_id in observation_ids:
            # Create Observation record
            record = ObservationRecord.objects.create(
                target=last_obs.target,
                facility=facility.name,
                parameters=json.dumps(observation_payload),
                observation_id=observation_id
            )
            self.observation_group.observation_records.add(record)
            self.observation_group.save()
            new_observations.append(record)

        for obsr in new_observations:
            facility = get_service_class(obsr.facility)()
            facility.update_observation_status(obsr.observation_id)

        return new_observations

    def advance_window(self, observation_payload, start_keyword='start', end_keyword='end'):
        new_start = parse(observation_payload[start_keyword]) + timedelta(hours=self.advance_window_hours)
        new_end = parse(observation_payload[end_keyword]) + timedelta(hours=self.advance_window_hours)
        observation_payload[start_keyword] = new_start.isoformat()
        observation_payload[end_keyword] = new_end.isoformat()

        return observation_payload


class CadenceForm(forms.Form):
    cadence_strategy = forms.ChoiceField(
        required=False,
        choices=[('', '---------')] + [(k, k) for k, v in get_cadence_strategies().items()]
    )
    cadence_frequency = forms.IntegerField(
        required=False,
        help_text='Frequency of observations, in hours'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cadence_strategy'].widget.attrs['readonly'] = True
        self.fields['cadence_frequency'].widget.attrs['readonly'] = True
        self.cadence_layout = self.cadence_layout()

    def cadence_layout(self):
        # If cadence strategy or cadence frequency aren't set, this is a normal observation and the widgets shouldn't
        # be rendered
        if not (self.initial.get('cadence_strategy') or self.initial.get('cadence_frequency')):
            return Layout()
        else:
            return Layout(
                Div(
                    HTML('<p>Reactive cadencing parameters. Leave blank if no reactive cadencing is desired.</p>'),
                ),
                Div(
                    Div(
                        'cadence_strategy',
                        css_class='col'
                    ),
                    Div(
                        'cadence_frequency',
                        css_class='col'
                    ),
                    css_class='form-row'
                )
            )
