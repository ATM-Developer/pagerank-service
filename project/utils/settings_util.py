import os
import configparser

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
cfg_path = os.path.join(BASE_DIR, 'project/settings.cfg')
config_parser = configparser.ConfigParser()
config_parser.read(cfg_path, encoding='utf-8')


def get_str(section, option, default=None, path_join=False):
    try:
        value = config_parser.get(section=section, option=option)
        if path_join:
            value = os.path.join(BASE_DIR, value)
    except:
        value = default
    return value


def get_int(section, option, default=None):
    try:
        value = config_parser.getint(section=section, option=option)
    except:
        value = default
    return value


def get_boolean(section, option, default=None):
    try:
        value = config_parser.getboolean(section=section, option=option)
    except:
        value = default
    return value


def get_float(section, option, default=None):
    try:
        value = config_parser.getfloat(section=section, option=option)
    except:
        value = default
    return value


def get_cfg(section, option, default=None, path_join=False):
    try:
        value = eval(config_parser.get(section=section, option=option))
        if path_join:
            value = os.path.join(BASE_DIR, value)
    except:
        value = default
    return value
