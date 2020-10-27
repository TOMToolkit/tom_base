from django import template


register = template.Library()


@register.inclusion_tag('tom_alerts/partials/submit_upstream_button.html')
def submit_upstream_button(broker, target=None, observation_record=None, redirect_url=None):
    """
    Renders a button to submit an alert upstream to a broker. At least one of target/obs record should be given.

    :param broker: The name of the broker to which the button will lead, as in the name field of the broker module.
    :type broker: str

    :param target: The target to be submitted as an alert, if any.
    :type target: ``Target``

    :param observation_record: The observation record to be submitted as an alert, if any.
    :type observation_record: ``ObservationRecord``

    :param redirect_url:
    :type redirect_url: str
    """
    # TODO: document this function somewhere prominent, as it likely won't live in the default templates
    return {
        'broker': broker,
        'target': target,
        'observation_record': observation_record,
        'redirect_url': redirect_url
    }
