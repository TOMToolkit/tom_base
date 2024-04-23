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
