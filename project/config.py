
import os
import logging
from project.utils.settings_util import config_parser, load_keystore, get_env_list, ENV_PATH, ENV_LOADED
from project.utils.logging_util import mask_rpc_urls

logger = logging.getLogger("main")


def _apply_private_rpc_overrides(chains):
    # Private RPC URLs (e.g. from a paid provider) go in .env instead of
    # settings.cfg so they never end up committed. PRIVATE_RPC_<CHAIN>,
    # comma-separated, is added to that chain's RPC pool alongside the public
    # ones (the pickers rank by latest block, so list order is not priority).
    # Duplicates are dropped: the pickers' used-uri reset assumes unique URIs.
    logger.info('.env {} ({})'.format('loaded' if ENV_LOADED else 'not found - using settings.cfg RPCs only', ENV_PATH))
    for chain, chain_config in chains.items():
        private_uris = list(dict.fromkeys(get_env_list('PRIVATE_RPC_{}'.format(chain.upper()))))
        if private_uris:
            chain_config['web3_provider_uri'] = list(dict.fromkeys(
                private_uris + chain_config.get('web3_provider_uri', [])))
            logger.info('{}: {} private RPC(s) added: {}'.format(
                chain, len(private_uris), mask_rpc_urls(private_uris)))


class Config:
    JSON_AS_ASCII = False

    SCHEDULER_API_ENABLED = False
    SCHEDULER_EXECUTORS = {
        "default": {'type': 'threadpool', 'max_workers': 1000}
    }
    SCHEDULER_JOB_DEFAULTS = {
        'coalesce': False,
        'max_instances': 3
    }

    X_CG_DEMO_API_KEY = os.getenv('CG_API_KEY')

    @staticmethod
    def init_app(app):
        pass


class ProductionConfig(Config):
    def __init__(self):
        for k, v in config_parser['setting'].items():
            self.__setattr__(k.upper(), eval(v))
        for k, v in config_parser['default'].items():
            self.__setattr__(k.upper(), eval(v))
        _apply_private_rpc_overrides(self.CHAINS)
        address, private_key = load_keystore(self.PRIVATE_PATH)
        self.__setattr__('WALLET_ADDRESS', address)
        self.__setattr__('WALLET_PRIVATE_KEY', private_key)


class DevelopmentConfig(Config):
    def __init__(self):
        for k, v in config_parser['setting'].items():
            self.__setattr__(k.upper(), eval(v))
        for k, v in config_parser['default'].items():
            self.__setattr__(k.upper(), eval(v))
        _apply_private_rpc_overrides(self.CHAINS)
        address, private_key = load_keystore(self.PRIVATE_PATH)
        self.__setattr__('WALLET_ADDRESS', address)
        self.__setattr__('WALLET_PRIVATE_KEY', private_key)


config = {
    'production': ProductionConfig,
    "development": DevelopmentConfig
}
