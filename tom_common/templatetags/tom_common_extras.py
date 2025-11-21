import textwrap
import logging

from django import template
from django.db.models import IntegerField
from django.db.models.functions import Cast
from django.conf import settings
from django_comments.models import Comment
from django.apps import apps
from django.core.exceptions import FieldDoesNotExist
from guardian.shortcuts import get_objects_for_user
from django.utils.module_loading import import_string

from tom_targets.models import Target

logger = logging.getLogger(__name__)

register = template.Library()


@register.inclusion_tag('tom_common/partials/navbar_app_addons.html', takes_context=True)
def navbar_app_addons(context, position='left'):
    """
    Imports the navbar content from appropriate apps
    Each nav_item should be contained in a list of dictionaries in an app's apps.py `nav_items` method.
    Each nav_item dictionary should contain a 'partial' key with the path to the html partial template and
    optionally a 'context' key with the path to the context processor class (typically a templatetag). An optional
    'position' key will add the partial to either the right or left side of the nav bar.

    FOR EXAMPLE:
    [{'partial': 'path/to/partial.html',
      'context': 'path/to/context/data/method',
      'position: 'left'}]
    """
    nav_items_to_display = []
    for app in apps.get_app_configs():
        try:
            nav_items = app.nav_items()
        except AttributeError:
            continue
        if nav_items:
            for item in nav_items:
                context_method_path = item.get('context', None)
                if context_method_path:
                    try:
                        context_method = import_string(item.get('context'))
                        new_context = context_method({})
                    except ImportError as e:
                        logger.warning(f'WARNING: Could not import context for {app.name} navbar item from '
                                       f'{item["context"]}: \n'
                                       f'{e}')
                        continue
                else:
                    new_context = {}
                if item.get('position', 'left') == position:
                    nav_items_to_display.append({'partial': item['partial'], 'context': new_context})

    context['nav_items_to_display'] = nav_items_to_display
    return context


@register.simple_tag
def comments_enabled():
    """
    Returns the TOM setting specifying whether or not comments are enabled
    """
    try:
        return settings.COMMENTS_ENABLED
    except AttributeError:
        return True


@register.simple_tag
def verbose_name(instance, field_name):
    """
    Displays the more descriptive field name from a Django model field
    """
    try:
        return instance._meta.get_field(field_name).verbose_name.title()
    except (FieldDoesNotExist, AttributeError):
        return field_name.title()


@register.simple_tag
def help_text(instance, field_name):
    """
    Displays the help text from a Django model field
    """
    return instance._meta.get_field(field_name).help_text


@register.inclusion_tag('comments/list.html', takes_context=True)
def recent_comments(context, limit=10):
    """
    Displays a list of the most recent comments in the TOM up to the given limit, or 10 if not specified.

    Comments will only be displayed for targets which the logged-in user has permission to view.
    """
    user = context['request'].user
    targets_for_user = get_objects_for_user(user, f'{Target._meta.app_label}.view_target')

    # In django-contrib-comments, the Comment model has a field ``object_pk`` which refers to the primary key
    # of the object it is related to, i.e., a comment on a ``Target`` has an ``object_pk`` corresponding with the
    # ``Target`` id. The ``object_pk`` is stored as a TextField.

    # In order to filter on ``object_pk`` with an iterable of ``IntegerFields`` using the ``in`` comparator,
    # we have to cast the ``object_pk`` to an int and annotate it as ``object_pk_as_int``.
    return {
        'comment_list': Comment.objects.annotate(
            object_pk_as_int=Cast('object_pk', output_field=IntegerField())
        ).filter(
            object_pk_as_int__in=targets_for_user
        ).order_by('-submit_date')[:limit]
    }


@register.filter
def truncate_value_for_display(value, width=12):
    """
    Limits the length and format of displayed values to width:

    Call using `{% value|truncate_value_for_display:width %}`

     - anything with characters less than or equal to the given width is displayed as-is
     - numbers longer than the width are truncated to that width digits if the number is between 10^-3 and 10^width
     - numbers outside that range are converted to scientific notation
     - Words larger than 50% over width characters are split and display is limited to 5 lines of text

    """

    if len(str(value)) <= width:
        return str(value)
    elif isinstance(value, float) or isinstance(value, int):
        if 10**width > abs(value) >= 0.001:
            return str(value)[:width]
        return "{:e}".format(value)
    else:
        word_length = int(width + width / 2)
        return textwrap.fill(str(value), width=word_length, max_lines=5, placeholder='...')


@register.filter
def multiplyby(value, arg):
    """
    Multiply the value by a number and return a float.
    `{% value|multiplyby:"x.y" %}`
    """
    return float(value) * float(arg)


@register.filter
def addstr(arg1, arg2):
    """
    Concatenate strings arg1 & arg2.
    This filter is necessary when adding strings because the default `|add:` will try to add the args as INTs first
    rather than concatenating them.
    Example:
    ``` {% some_var|addstr:'string' %} ```
    """
    return str(arg1) + str(arg2)


@register.simple_tag
def tom_name():
    return getattr(settings, 'TOM_NAME', 'TOM Toolkit')


@register.inclusion_tag('tom_common/partials/copy_button.html')
def copy_button(text_to_copy='', help_text='Copy'):
    """Uses the `copy_button.html` partial to copy the `text_to_copy` to the clipboard.
    The `help_text` is displayed as a tooltip when hovering over the button.
    Use this tag to include a low-profile copy button in your template.
    Example:
    ```{% copy_button 'text to be copied' 'Help Text' %}```
    """
    return {'copy_text': str(text_to_copy),
            'copy_help': str(help_text)}


@register.inclusion_tag('tom_common/partials/include_app_partial.html', takes_context=True)
def show_individual_app_partial(context, app_partial_data):
    """
    An Inclusion tag for setting the unique context for an app's partial.
    """
    for item in app_partial_data['context']:
        context[item] = app_partial_data['context'][item]
    context['app_partial'] = app_partial_data['partial']
    return context


@register.simple_tag
def get_theme():
    """Check for theme in settings.py"""
    theme = getattr(settings, 'CSS_THEME', None)
    if theme is not None:
        return f'tom_common/css/{theme.lower()}.css'
    return None
