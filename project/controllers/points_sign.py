# get the points signature - isolated from the withdraw (prefetching) api

from project.controllers.base_import import *
from project.services.points_sign_service import check_points_addresses, check_points_balance, check_points_interval, \
    save_points_interval, get_points_transfer_address, get_chain_id, get_points_sign, get_points_code, parse_points, MAX_EXPIRATION_SECONDS

bpoints_sign = Blueprint('points_sign', __name__)


def _address(value):
    if not value or not isinstance(value, str) or not Web3.isAddress(value.strip()):
        return None
    return Web3.toChecksumAddress(value.strip())


@bpoints_sign.route('/transfer', methods=['POST'])
def get_points_signature():
    # only executer and senators provide this api
    web3eth = Web3Eth(logger, jitter=False)
    if not web3eth.is_senators_or_executer():
        logger.info('self not executer or senator.')
        return response(ResponseCode.NOT_SENATORS)
    req_param = request.get_json(silent=True) or {}
    logger.info('get the points sign: {}'.format(req_param))

    # PointsTransfer contract: POINTS_TRANSFER_ADDRESS, or looked up on the GameHub when empty
    requested_transfer = req_param.get('transferContract')
    requested_transfer_address = _address(requested_transfer)
    if requested_transfer and not requested_transfer_address:
        logger.info('params error.')
        return response(ResponseCode.PARAMS_ERROR)
    transfer_address, err = get_points_transfer_address(web3eth, requested_transfer_address)
    if not transfer_address:
        logger.info('points transfer contract check failed: {}'.format(err))
        return jsonify(err)

    source = _address(req_param.get('source'))
    destination = _address(req_param.get('destination'))
    invoked_by = _address(req_param.get('invokedBy'))
    contract_address = _address(req_param.get('contract'))
    points = parse_points(req_param.get('points'))
    timestamp = req_param.get('timestamps')
    if not source or not destination or not invoked_by or not contract_address or points is None \
            or not isinstance(timestamp, int) or isinstance(timestamp, bool):
        logger.info('params error.')
        return response(ResponseCode.PARAMS_ERROR)
    source_key = source.lower()

    ok, err = check_points_addresses(web3eth, source, destination, invoked_by, contract_address)
    if not ok:
        logger.info('points address check failed: {}'.format(err))
        return jsonify(err)

    chain_id = get_chain_id(web3eth)
    req_chain_id = req_param.get('chainId')
    if req_chain_id is not None and str(req_chain_id) != str(chain_id):
        logger.info('chain id {} not match node chain id {}'.format(req_chain_id, chain_id))
        return response(ResponseCode.PARAMS_ERROR)

    # one signature per source in a period of time
    if not check_points_interval(source_key):
        logger.info('it is not time, please wait.')
        return response(ResponseCode.PLEASE_WAIT)

    now_timestamp = int(get_now_timestamp())
    if timestamp < now_timestamp:
        logger.info('timestamp {} lt now timestamp {}'.format(timestamp, now_timestamp))
        return jsonify({'errcode': -1, 'errmsg': 'timestamp {} lt now timestamp {}'.format(timestamp, now_timestamp)})
    overdue_timestamp = min(timestamp, now_timestamp + MAX_EXPIRATION_SECONDS)

    # points checking start
    ok, err = check_points_balance(source, points, web3eth, contract_address)
    if not ok:
        logger.info('points check failed: {}'.format(err))
        return jsonify(err)
    # points checking end

    # provide sign string
    sign_str, nonce, raw_sign, points_wei = get_points_sign(web3eth, transfer_address, source, destination,
                                                            invoked_by, contract_address, points, overdue_timestamp,
                                                            chain_id)
    code = get_points_code(web3eth, source, destination, invoked_by, contract_address, points_wei,
                           overdue_timestamp, raw_sign)

    res = {'errcode': 0, 'data': {'sign': sign_str, 'nonce': nonce, 'expected_expiration': overdue_timestamp,
                                  'code': code, 'chain_id': chain_id,
                                  'transfer_contract': transfer_address}}
    if current_app.config_name == 'development':
        res['debug'] = raw_sign
    logger.info('points sign result: {}'.format(res))
    save_points_interval(source_key, overdue_timestamp)
    return jsonify(res)
