import os
from yaml import safe_load


class Params():
    def __init__(self):
        base_path = os.path.dirname(os.path.dirname(__file__))
        self.config_yaml_path = os.path.join(base_path, 'Configs/config.yaml')
        self.params = {}
        self.read_yaml()

    def read_yaml(self):
        with open(self.config_yaml_path, 'r') as rf:
            self.params = safe_load(rf)

        for k, v in self.params.items():
            self.__setattr__(k, v)


params = Params()
