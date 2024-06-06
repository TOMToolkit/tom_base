import logging

from django.conf import settings
from rest_framework.routers import DefaultRouter, SimpleRouter

logger = logging.getLogger(__name__)


class SharedAPIRootRouter(SimpleRouter):
    shared_router = DefaultRouter()

    def register(self, *args, **kwargs):
        logger.info(f'registering new views: args: {args}, kwargs: {kwargs}')
        viewset = kwargs.get('viewset') or args[1]
        basename = kwargs.get('basename') or args[2] if len(args) > 2 else None
        if not basename:
            basename = self.shared_router.get_default_basename(viewset)
        if self.shared_router.is_already_registered(basename):
            logger.warning(
                f'Cannot register new views: args: {args}, kwargs: {kwargs} -> {basename} is already registered'
            )
        else:
            self.shared_router.register(*args, **kwargs)
            super().register(*args, **kwargs)


def collect_api_urls():
    """
    Import the urls.py module from each INSTALLED_APP so that each app can register
    it's REST API ViewSets with the single SharedAPIRootRouter().

    Conventions assumed:
    1. Your app is added to the INSTALLED_APPS list as '<your_app>' (and not using the django.apps.AppConfig subclass).
    2. Your app's `urls.py` is top-level and named `urls.py`

    Upon `import`, your REST API urls and views will be registered with the singleton rest_framework.DefaultRouter
    defined as `tom_common.api_router.SharedAPIRootRouter as long as you register them in your `urls.py`.
    In the `<your_app>/urls.py` it should look like this:

    ```python
    from tom_common.api_router import SharedAPIRootRouter
    router = SharedAPIRootRouter()
    router.register(r'your_app', YourAppModelViewSet)
    ```
    :return: list of router.urls collected from all INSTALLED_APPS with urls.py modules
    """
    from importlib import import_module
    for app in settings.INSTALLED_APPS:
        logger.debug(f'looking in {app} for urls.py')
        try:
            import_module(app + '.urls')  # by convention where the REST API routes are defined.
        except (ImportError, AttributeError) as err:
            logger.debug(f'Failed to import urls from {app} err: {err}')
    return SharedAPIRootRouter.shared_router.urls
