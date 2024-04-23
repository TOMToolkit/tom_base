from tom_targets.base_models import TargetMatchManager


class StrictMatch(TargetMatchManager):
    """
    Return Queryset for target with name matching string.
    """

    def get_name_match(self, name):
        """
        Returns a queryset exactly matching name that is received
        :param name: The string against which target names will be matched.
        :return: queryset containing matching Target(s).
        """
        queryset = self.check_for_exact_name_match(name)
        return queryset


class ConeSearchManager(TargetMatchManager):
    """
    Return Queryset for target with name matching string.
    """

    def check_unique(self, target, *args, **kwargs):
        """
        Returns a queryset containing any targets that are both a fuzzy match and within 2 arcsec of
        the target that is received
        :param target: The target object to be checked.
        :return: queryset containing matching Target(s).
        """
        queryset = super().check_unique(target, *args, **kwargs)
        radius = 2
        cone_search_queryset = self.check_for_nearby_match(target.ra, target.dec, radius)
        return queryset | cone_search_queryset
