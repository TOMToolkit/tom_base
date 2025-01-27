from typing import Any

from bootstrap4.templatetags.bootstrap4 import get_pagination_context, register
from django.conf import settings
from django.core.paginator import Page


@register.inclusion_tag("bootstrap4_overrides/pagination.html")
def bootstrap_pagination(page: Page, **kwargs) -> dict[str, Any]:
    """Render a Bootstrap pagination component with additional context. This function
    extends the default pagination context to include the start index, end index, and
    total count of items.

    Parameters
    ----------
    page : `Page`
        The page of results to show.

    Returns
    -------
    `dict`
        The context for rendering the pagination component, including
        pagination details and item counts.
    """
    pagination_kwargs = kwargs.copy()
    pagination_kwargs["page"] = page

    # Get the default pagination context.
    context = get_pagination_context(**pagination_kwargs)

    # Add item counts to the context.
    context["start_index"] = page.start_index()
    context["end_index"] = page.end_index()
    context["total_count"] = page.paginator.count
    context["show_pagination_info"] = getattr(settings, "SHOW_PAGINATION_INFO", True)
    return context
