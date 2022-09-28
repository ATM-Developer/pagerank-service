# get the prefetching signature

from project.controllers.base_import import *
from project.services.assets_service import check_prefetching_interval, save_prefetching_interval

bsign = Blueprint('sign', __name__)


@bsign.route('/prefetching', methods=['POST'])
def get_sign_main_coin():
    # only executer and senators provide this api
    web3eth = Web3Eth(logger)
    if not web3eth.is_senators_or_executer():
        logger.info('self not executer or senator.')
        return response(ResponseCode.NOT_SENATORS)
    req_param = request.get_json()
    logger.info('get the main coin sign: {}'.format(req_param))
    user_address = req_param.get('user_address')
    user_address = user_address.lower()
    contract_address = req_param.get('contract_address')
    timestamp = req_param.get('timestamps')
    amount = Decimal(str(req_param.get('amount', 0)))
    if not user_address or not str(user_address).strip() or amount <= 0 \
            or not contract_address or not str(contract_address).strip():
        logger.info('params error.')
        return response(ResponseCode.PARAMS_ERROR)

    # users can only withdraw income once in a period of time
    if not check_prefetching_interval(user_address, 'luca'):
        logger.info('it is not time, please wait.')
        return response(ResponseCode.PLEASE_WAIT)

    now_timestamp = int(get_now_timestamp())
    if not timestamp or timestamp < now_timestamp:
        logger.info('timestamp {} lt now timestamp {}'.format(timestamp, now_timestamp))
        return {'errcode': -1, 'errmsg': 'timestamp {} lt now timestamp {}'.format(timestamp, now_timestamp)}
    if timestamp > now_timestamp + 3600:
        overdue_timestamp = now_timestamp + 3600
    else:
        overdue_timestamp = timestamp

    # verify whether the amount of assets is equal
    user_assets = Assets(user_address, web3eth).get()
    assets = user_assets['luca']['total']
    logger.info('address: {}, assets: {}'.format(user_assets, assets))
    if amount != assets:
        res = {'errcode': -1, 'errmsg': 'not all assets.'}
        logger.info('not all assets.')
        return jsonify(res)
    # provide sign string
    sign_str, nonce, raw_sign = web3eth.get_sign(Web3.toChecksumAddress(user_address), amount, contract_address,
                                                 overdue_timestamp)

    res = {'errcode': 0, 'data': {"sign": sign_str, 'nonce': nonce, 'expected_expiration': overdue_timestamp}}
    if current_app.config_name == 'development':
        res['debug'] = raw_sign
    logger.info('sign result: {}'.format(res))
    save_prefetching_interval(user_address, 'luca', overdue_timestamp)
    return jsonify(res)


@bsign.route('/other/prefetching', methods=['POST'])
def get_sign_subcoin():
    # only executer and senators provide this api
    web3eth = Web3Eth(logger)
    if not web3eth.is_senators_or_executer():
        logger.info('self not executer or senator.')
        return response(ResponseCode.NOT_SENATORS)
    req_param = request.get_json()
    logger.info('get the subcoin sign: {}'.format(req_param))
    user_address = req_param.get('user_address')
    contract_address = req_param.get('contract_address')
    timestamp = req_param.get('timestamps')
    coin_type = req_param.get('coin_type')
    coin_type = coin_type.lower()
    amount = Decimal(str(req_param.get('amount', 0)))
    if not user_address or not str(user_address).strip() or not coin_type or amount <= 0 \
            or not contract_address or not str(contract_address).strip():
        logger.info('params error.')
        return response(ResponseCode.PARAMS_ERROR)

    # users can only withdraw income once in a period of time
    if not check_prefetching_interval(user_address, coin_type):
        logger.info('it is not time, please wait.')
        return response(ResponseCode.PLEASE_WAIT)

    now_timestamp = int(get_now_timestamp())
    if not timestamp or timestamp < now_timestamp:
        logger.info('timestamp {} lt now timestamp {}'.format(timestamp, now_timestamp))
        return {'errcode': -1, 'errmsg': 'timestamp {} lt now timestamp {}'.format(timestamp, now_timestamp)}
    if timestamp > now_timestamp + 3600:
        overdue_timestamp = now_timestamp + 3600
    else:
        overdue_timestamp = timestamp
    # verify whether the amount of assets is equal
    user_assets = Assets(user_address, web3eth, coin_type=coin_type).get()
    assets = user_assets[coin_type]['total']
    if amount != assets:
        res = {'errcode': -1, 'errmsg': 'not all assets.'}
        logger.info('not all assets.')
        return jsonify(res)
    # provide sign string
    sign_str, nonce, raw_sign = web3eth.get_sign(Web3.toChecksumAddress(user_address), amount, contract_address,
                                                         overdue_timestamp)

    res = {'errcode': 0, 'data': {"sign": sign_str, 'nonce': nonce, 'expected_expiration': overdue_timestamp}}
    if current_app.config_name == 'development':
        res['debug'] = raw_sign
    logger.info('sign result: {}'.format(res))
    save_prefetching_interval(user_address, coin_type, overdue_timestamp)
    return jsonify(res)
