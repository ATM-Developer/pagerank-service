import os
import logging.config

log_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {
            "format": "%(asctime)s - %(levelname)s - [%(funcName)s-%(lineno)s]: %(message)s"
        },
        "thread_": {
            "format": "%(asctime)s - %(levelname)s - %(threadName)s-%(thread)d - [%(funcName)s-%(lineno)s]: %(message)s"
        }
    },
    "handlers": {
        "main": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "INFO",
            "formatter": "thread_",
            "filename": os.path.join(os.path.dirname(os.path.dirname(__file__)), 'log/main.log'),
            "maxBytes": 10485760,
            "backupCount": 20,
            "encoding": "utf8"
        },
        "calculate": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "INFO",
            "formatter": "thread_",
            "filename": os.path.join(os.path.dirname(os.path.dirname(__file__)), 'log/calculate.log'),
            "maxBytes": 10485760,
            "backupCount": 20,
            "encoding": "utf8"
        }
    },
    "loggers": {
        "main": {
            "level": "INFO",
            "handlers": ["main"]
        },
        "calculate": {
            "level": "INFO",
            "handlers": ["calculate"]
        }
    }
}

log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'log')
if not os.path.exists(log_dir):
    try:
        os.makedirs(log_dir)
    except:
        pass
logging.config.dictConfig(log_config)
