from django.db import models


class StrictMatch(models.Manager):
    """
    Return Queryset for target with name matching string.
    """

    def check_for_fuzzy_match(self, name):
        """
        Returns a queryset exactly matching name that is received
        :param name: The string against which target names will be matched.
        :return: queryset containing matching Target(s).
        """
        queryset = super().get_queryset().filter(name=name)
        return queryset
