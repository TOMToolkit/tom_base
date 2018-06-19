import os
from importlib import import_module


class CatalogHarvester(object):
    def __init__(self, *args, **kwargs):
        self.modules = {}
        for plugin in os.listdir(os.path.dirname(__file__)):
            if plugin[-3:] == '.py' and plugin not in ['__init__.py', 'loader.py']:
                mod = import_module('.' + plugin[:-3], 'tom_catalogs.harvesters')
                mod.register(self)

    def register(self, clz, name):
        print('loading ' + name)
        self.modules[name] = clz
