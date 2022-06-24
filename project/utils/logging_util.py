import os
import logging
import logging.config

from project.utils.settings_util import get_cfg


def base_handler(file_name):
    return {
        "class": "logging.handlers.RotatingFileHandler",
        "level": "INFO",
        "formatter": "thread_",
        "filename": os.path.join(get_cfg('setting', 'log_dir', path_join=True), file_name),
        "maxBytes": 10485760,
        "backupCount": 20,
        "encoding": "utf8"
    }


def base_logger(logger_name):
    return {
        "level": "INFO",
        "handlers": [logger_name]
    }


logging_json = {
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
        "main": base_handler("main.log"),
        "calculate": base_handler("calculate.log"),
        "earnings_top_nodes": base_handler("earnings_top_nodes.log"),
        "earnings_pr": base_handler("earnings_pr.log"),
        "earnings_net_pr": base_handler("earnings_net_pr.log"),
        "earnings_alone_pr": base_handler("earnings_alone_pr.log"),
        "earnings_pledge": base_handler("earnings_pledge.log"),
        "earnings_trans": base_handler("earnings_trans.log"),
        "data_job": base_handler("data_job.log"),
        "binance_pledge": base_handler("binance_pledge.log"),
        "matic_pledge": base_handler("matic_pledge.log"),
        "liquidity_data": base_handler("liquidity_data.log"),
        "prefetching_events": base_handler("prefetching_events.log"),
        "prefetching_chain": base_handler("prefetching_chain.log"),
        "del_old_datas": base_handler("del_old_datas.log"),
        "reset_time": base_handler("reset_time.log"),
    },
    "loggers": {
        "main": base_logger("main"),
        "calculate": base_logger("calculate"),
        "earnings_top_nodes": base_logger("earnings_top_nodes"),
        "earnings_pr": base_logger("earnings_pr"),
        "earnings_net_pr": base_logger("earnings_net_pr"),
        "earnings_alone_pr": base_logger("earnings_alone_pr"),
        "earnings_pledge": base_logger("earnings_pledge"),
        "earnings_trans": base_logger("earnings_trans"),
        "data_job": base_logger("data_job"),
        "binance_pledge": base_logger("binance_pledge"),
        "matic_pledge": base_logger("matic_pledge"),
        "liquidity_data": base_logger("liquidity_data"),
        "prefetching_events": base_logger("prefetching_events"),
        "prefetching_chain": base_logger("prefetching_chain"),
        "del_old_datas": base_logger("del_old_datas"),
        "reset_time": base_logger("reset_time"),
    }
}


def load_json():
    log_dir = get_cfg('setting', 'log_dir', path_join=True)
    if not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir)
        except:
            pass
    logging.config.dictConfig(logging_json)
    return True
