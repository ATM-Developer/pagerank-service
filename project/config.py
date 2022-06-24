from project.utils.settings_util import config_parser


class Config:
    JSON_AS_ASCII = False

    SCHEDULER_API_ENABLED = True
    SCHEDULER_EXECUTORS = {
        "default": {'type': 'threadpool', 'max_workers': 1000}
    }
    SCHEDULER_JOB_DEFAULTS = {
        'coalesce': False,
        'max_instances': 3
    }

    @staticmethod
    def init_app(app):
        pass


class ProductionConfig(Config):
    def __init__(self):
        for k, v in config_parser['setting'].items():
            self.__setattr__(k.upper(), eval(v))
        for k, v in config_parser['default'].items():
            self.__setattr__(k.upper(), eval(v))


class DevelopmentConfig(Config):
    def __init__(self):
        for k, v in config_parser['setting'].items():
            self.__setattr__(k.upper(), eval(v))
        for k, v in config_parser['default'].items():
            self.__setattr__(k.upper(), eval(v))


config = {
    'production': ProductionConfig,
    "development": DevelopmentConfig
}
