from django.apps import AppConfig


class TomTargetsConfig(AppConfig):
    name = 'tom_targets'

    def ready(self):
        import tom_targets.signals.handlers  # noqa
        super().ready()
