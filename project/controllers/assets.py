# get the withdrawal amount

from project.controllers.base_import import *

assets = Blueprint('assets', __name__)


@assets.route('/info', methods=['POST'])
def get_assets_main_coin():
    req_params = request.get_json()
    logger.info('assets info main coin: {}'.format(req_params))

    user_address = req_params.get('user_address')
    if not user_address or not str(user_address).strip():
        return response(ResponseCode.PARAMS_ERROR)

    # only executer provides this api
    web3eth = Web3Eth(logger)
    if not web3eth.is_executer():
        logger.info('self not executer.')
        return response(ResponseCode.NOT_EXECUTER)

    assets = Assets(user_address, web3eth).get()
    for k, v in assets.items():
        for k1, v1 in v.items():
            v[k1] = float(v1)
    logger.info('user: {}, assets: {}'.format(user_address, assets))
    return response(ResponseCode.SUCCESS, data=assets['luca'])


@assets.route('/other/info', methods=['POST'])
def get_other_subcoin():
    req_params = request.get_json()
    logger.info('assets info subnet coin: {}'.format(req_params))

    user_address = req_params.get('user_address')
    coin_type = req_params.get('coin_type')
    if not user_address or not str(user_address).strip() or not coin_type:
        return response(ResponseCode.PARAMS_ERROR)
    # only executer provides this api
    web3eth = Web3Eth(logger)
    if not web3eth.is_executer():
        logger.info('self not executer.')
        return response(ResponseCode.NOT_EXECUTER)
    coin_type = coin_type.lower()

    assets = Assets(user_address, web3eth, coin_type=coin_type).get()
    for k, v in assets.items():
        for k1, v1 in v.items():
            v[k1] = float(v1)
    logger.info('user: {}, assets: {}'.format(user_address, assets))
    return response(ResponseCode.SUCCESS, data=assets[coin_type])
