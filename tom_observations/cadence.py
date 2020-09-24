from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from dateutil.parser import parse
from importlib import import_module
import json

from crispy_forms.layout import Column, Div, HTML, Layout, Row
from django import forms
from django.conf import settings


DEFAULT_CADENCE_STRATEGIES = [
    'tom_observations.cadences.retry_failed_observations.RetryFailedObservationsStrategy',
    'tom_observations.cadences.resume_cadence_after_failure.ResumeCadenceAfterFailureStrategy'
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
    def __init__(self, dynamic_cadence, *args, **kwargs):
        self.cadence_strategy = type(self).__name__
        self.dynamic_cadence = dynamic_cadence

    @abstractmethod
    def run(self):
        pass


class CadenceForm(forms.Form):
    # TODO: review this
    cadence_strategy = forms.CharField(required=True, max_length=50, widget=forms.HiddenInput())
    # cadence_strategy = forms.ChoiceField(
    #     required=False,
    #     choices=[('', '---------')] + [(k, k) for k, v in get_cadence_strategies().items()]
    # )
    cadence_frequency = forms.IntegerField(
        required=False,
        help_text='Frequency of observations, in hours'
    )

    def __init__(self, *args, **kwargs):
        print(kwargs)
        super().__init__(*args, **kwargs)
        # self.fields['cadence_strategy'].widget.attrs['readonly'] = True
        self.fields['cadence_frequency'].widget.attrs['readonly'] = True
        self.cadence_layout = self.cadence_layout()

    def cadence_layout(self):
        # If cadence strategy or cadence frequency aren't set, this is a normal observation and the widgets shouldn't
        # be rendered
        if not (self.initial.get('cadence_strategy') or self.initial.get('cadence_frequency')):
            return Layout()
        else:
            # TODO: Clarify dynamic vs. static cadencing in form
            # TODO: Present layout for selected cadence strategy
            return Layout(
                Div(
                    HTML('<p>Dynamic cadencing parameters. Leave blank if no dynamic cadencing is desired.</p>'),
                ),
                Div(
                    Div(
                        'cadence_frequency',
                        css_class='col'
                    ),
                    css_class='form-row'
                )
            )

    extra_layout = cadence_layout
