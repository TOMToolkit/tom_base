from django.apps import AppConfig


class TomCatalogsConfig(AppConfig):
    name = 'tom_catalogs'

    def harvester_classes(self):
        """
        Integration point for adding harvester classes to the dropdown options when ingesting targets from Catalogs.
        This method should return a list of dot separated harvester classes.
        """
        DEFAULT_HARVESTER_CLASSES = [
            'tom_catalogs.harvesters.simbad.SimbadHarvester',
            'tom_catalogs.harvesters.ned.NEDHarvester',
            'tom_catalogs.harvesters.jplhorizons.JPLHorizonsHarvester',
            'tom_catalogs.harvesters.tns.TNSHarvester',
        ]
        return DEFAULT_HARVESTER_CLASSES
