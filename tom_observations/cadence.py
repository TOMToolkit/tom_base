from abc import ABC, abstractmethod
from importlib import import_module

from crispy_forms.layout import Div, HTML, Layout, Row
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
        raise ImportError('''Could not a find a cadence strategy with that name.
                              Did you add it to TOM_CADENCE_STRATEGIES?''')


class CadenceStrategy(ABC):
    """
    The CadenceStrategy interface provides the methods necessary to implement a custom cadence strategy. All
    CadenceStrategies should inherit from this base class.

    In order to make use of a custom CadenceStrategy, add the path to ``TOM_CADENCE_STRATEGIES`` in your
    ``settings.py``.
    """
    def __init__(self, dynamic_cadence, *args, **kwargs):
        self.dynamic_cadence = dynamic_cadence

    @abstractmethod
    def run(self):
        pass


class CadenceForm(forms.Form):
    cadence_strategy = forms.CharField(required=False, max_length=50, widget=forms.HiddenInput())

    def cadence_layout(self):
        return Layout()


class BaseCadenceForm(CadenceForm):
    cadence_frequency = forms.IntegerField(
        required=True,
        help_text='Frequency of observations, in hours'
    )
    cadence_fields = set(['cadence_frequency'])

    def cadence_layout(self):
        return Layout(
            Div(
                HTML('''<p>Dynamic cadencing parameters. Leave blank if no dynamic cadencing is desired.
                        For more information on dynamic cadencing, see
                        <a href=\'https://tom-toolkit.readthedocs.io/en/stable/observing/strategies.html\'>
                        here.</a></p>'''),
            ),
            Row('cadence_strategy'),
            Row('cadence_frequency'),
        )
