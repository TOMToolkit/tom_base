class AbstractHarvester(object):
    name = 'ABSTRACT_HARVESTER'

    def __init__(self, *args, **kwargs):
        self.catalog_data = {}

    def query(self, term):
        self.term = term

    def to_target(self):
        raise NotImplementedError
