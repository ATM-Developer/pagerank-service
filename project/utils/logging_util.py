import os
import re
import logging
import logging.config
from urllib.parse import urlsplit, urlunsplit

from project.utils.settings_util import get_cfg

# Matches opaque API-key/token-like path segments (long unbroken alphanumeric
# runs with both letters and digits) - not human-readable path identifiers
# like 'bsc-mainnet' or 'polygon-mainnet', which use hyphens and stay visible
# so the endpoint can still be told apart in logs.
_SECRET_SEGMENT_RE = re.compile(r'^[0-9a-zA-Z]{16,}$')


def mask_secret(value, visible=4):
    """Redacts a secret-like string to its first/last `visible` chars
    (e.g. 'abcd****wxyz'), so it can still be recognised in logs without
    exposing the whole value."""
    if not value:
        return value
    value = str(value)
    if len(value) <= visible * 2:
        return '*' * len(value)
    return '{}****{}'.format(value[:visible], value[-visible:])


def _looks_like_secret(segment):
    return bool(_SECRET_SEGMENT_RE.match(segment)) \
        and any(c.isdigit() for c in segment) and any(c.isalpha() for c in segment)


def mask_rpc_url(url):
    """Masks any credentials/API keys embedded in an RPC URL's path or query
    (e.g. '.../v1/<api-key>') while keeping the scheme/host and any plain
    path identifiers visible, so the endpoint can still be identified in
    logs without leaking the secret."""
    if not url:
        return url
    parts = urlsplit(url)
    path = '/'.join(mask_secret(seg) if _looks_like_secret(seg) else seg for seg in parts.path.split('/'))
    query = mask_secret(parts.query) if parts.query else parts.query
    return urlunsplit((parts.scheme, parts.netloc, path, query, ''))


def mask_rpc_urls(urls):
    return [mask_rpc_url(u) for u in urls]


def base_handler(file_name, formatter="thread_"):
    return {
        "class": "logging.handlers.RotatingFileHandler",
        "level": "INFO",
        "formatter": formatter,
        "filename": os.path.join(get_cfg('setting', 'log_dir', path_join=True), file_name),
        "maxBytes": 10485760,
        "backupCount": get_cfg('setting', 'log_count'),
        "encoding": "utf8"
    }


def base_logger(logger_name):
    return {
        "level": "INFO",
        "handlers": [logger_name]
    }


def load_json():
    log_dir = get_cfg('setting', 'log_dir', path_join=True)
    if not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir)
        except:
            pass
    logging_json = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "simple": {
                "format": "%(asctime)s - %(levelname)s - [%(funcName)s-%(lineno)s]: %(message)s"
            },
            "thread_": {
                "format": "%(asctime)s - %(levelname)s - %(threadName)s-%(thread)d - [%(funcName)s-%(lineno)s]: %(message)s"
            },
            "process_": {
                "format": "%(asctime)s - %(levelname)s - pid=%(process)d - %(threadName)s-%(thread)d - [%(funcName)s-%(lineno)s]: %(message)s"
            }
        },
        "handlers": {
            "main": base_handler("main.log"),
            "process": base_handler("process.log", formatter="process_"),
            "calculate": base_handler("calculate.log"),
            "earnings_top_nodes": base_handler("earnings_top_nodes.log"),
            "earnings_pr": base_handler("earnings_pr.log"),
            "earnings_net_pr": base_handler("earnings_net_pr.log"),
            "earnings_alone_pr": base_handler("earnings_alone_pr.log"),
            "earnings_pledge": base_handler("earnings_pledge.log"),
            "earnings_trans": base_handler("earnings_trans.log"),
            "data_job": base_handler("data_job.log"),
            "boost_memory": base_handler("boost_memory.log"),
            "calculate_boost": base_handler("calculate_boost.log"),
            "reward_boost_pr": base_handler("reward_boost_pr.log"),
            "boost_data": base_handler("boost_data.log"),
            "boost_pr": base_handler("boost_pr.log"),
            "boost_rewards": base_handler("boost_rewards.log"),
            # "binance_pledge": base_handler("binance_pledge.log"),
            # "matic_pledge": base_handler("matic_pledge.log"),
            "liquidity_data": base_handler("liquidity_data.log"),
            "liquidity_data_usdc": base_handler("liquidity_data_usdc.log"),
            "prefetching_events": base_handler("prefetching_events.log"),
            "prefetching_chain": base_handler("prefetching_chain.log"),
            "del_old_datas": base_handler("del_old_datas.log"),
            "reset_time": base_handler("reset_time.log"),
            "upgrade_job": base_handler("upgrade_job.log"),
            "upgrade": base_handler("upgrade.log"),
        },
        "loggers": {
            "main": base_logger("main"),
            "process": base_logger("process"),
            "calculate": base_logger("calculate"),
            "earnings_top_nodes": base_logger("earnings_top_nodes"),
            "earnings_pr": base_logger("earnings_pr"),
            "earnings_net_pr": base_logger("earnings_net_pr"),
            "earnings_alone_pr": base_logger("earnings_alone_pr"),
            "earnings_pledge": base_logger("earnings_pledge"),
            "earnings_trans": base_logger("earnings_trans"),
            "data_job": base_logger("data_job"),
            "boost_memory": base_logger("boost_memory"),
            "calculate_boost": base_logger("calculate_boost"),
            "reward_boost_pr": base_logger("reward_boost_pr"),
            "boost_data": base_logger("boost_data"),
            "boost_pr": base_logger("boost_pr"),
            "boost_rewards": base_logger("boost_rewards"),
            # "binance_pledge": base_logger("binance_pledge"),
            # "matic_pledge": base_logger("matic_pledge"),
            "liquidity_data": base_logger("liquidity_data"),
            "liquidity_data_usdc": base_logger("liquidity_data_usdc"),
            "prefetching_events": base_logger("prefetching_events"),
            "prefetching_chain": base_logger("prefetching_chain"),
            "del_old_datas": base_logger("del_old_datas"),
            "reset_time": base_logger("reset_time"),
            "upgrade_job": base_logger("upgrade_job"),
            "upgrade": base_logger("upgrade"),
        }
    }
    chains = get_cfg('default', 'CHAINS')
    for k in chains.keys():
        logging_json['handlers']['{}_pledge'.format(k)] = base_handler('{}_pledge.log'.format(k))
        logging_json['loggers']['{}_pledge'.format(k)] = base_logger('{}_pledge'.format(k))
    logging.config.dictConfig(logging_json)
    return True
