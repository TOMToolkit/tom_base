import logging
from importlib import import_module

from django.conf import settings

logger = logging.getLogger(__name__)


def import_method(name):
    mod_name, method = name.rsplit('.', 1)
    try:
        mod = import_module(mod_name)
        m = getattr(mod, method)
    except (ImportError, AttributeError):
        raise ImportError('Could not import {}. Did you provide the correct path?'.format(name))
    return m


def run_hook(name, *args, **kwargs):
    hook = settings.HOOKS.get(name)
    if hook:
        method = import_method(hook)
        return method(*args, **kwargs)


def target_post_save(target, created):
    logger.info('Target post save hook: %s created: %s', target, created)


def observation_change_state(observation, previous_state):
    logger.info('Observation change state hook: %s from %s to %s', observation, previous_state, observation.status)
