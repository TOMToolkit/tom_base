from django import template

from tom_alerts.alerts import get_service_class

register = template.Library()


@register.inclusion_tag('tom_alerts/partials/submit_upstream_form.html')
def submit_upstream_form(broker, target=None, observation_record=None, redirect_url=None):
    """
    Renders a form to submit an alert upstream to a broker.
    At least one of target/obs record should be given.

    :param broker: The name of the broker to which the button will lead, as in the name field of the broker module.
    :type broker: str

    :param target: The target to be submitted as an alert, if any.
    :type target: ``Target``

    :param observation_record: The observation record to be submitted as an alert, if any.
    :type observation_record: ``ObservationRecord``

    :param redirect_url:
    :type redirect_url: str
    """
    broker_class = get_service_class(broker)
    form_class = broker_class.alert_submission_form
    form = form_class(broker=broker, initial={
        'target': target,
        'observation_record': observation_record,
        'redirect_url': redirect_url
    })

    return {
        'submit_upstream_form': form
    }
