# points signature service - isolated copy of the withdraw (prefetching) signing flow.
# Nothing here is shared with assets_service / Web3Eth.get_sign, so changes stay local.

import os
import json
from decimal import Decimal

from web3 import Web3
from eth_abi import encode_abi
from eth_account.messages import encode_defunct

from project.extensions import logger, app_config
from project.configs.eth.eth_config import POINTS_TRANSFER_ABI, GAME_HUB_ABI, DAILY_SESSION_MANAGER_ABI, \
    ACCESS_CONTROL_ABI
from project.utils.date_util import get_now_timestamp, time_format
from project.utils.settings_util import get_cfg

data_dir = get_cfg('setting', 'data_dir', path_join=True)
# own directory, so the lock never collides with the luca/subcoin withdraw lock
interval_dir = os.path.join(data_dir, 'points_sign', 'interval')

# max signature lifetime
MAX_EXPIRATION_SECONDS = 600
# wait after a signature before the same source can sign again
INTERVAL_SECONDS = 60
# smallest transfer - keeps points (1e18 scaled) above the expiration timestamp used in the code hash
MIN_POINTS = Decimal('0.000001')

ZERO_ADDRESS = '0x' + '0' * 40
# how far back to look for a populated pr.json (max claimable points tiers)
PR_LOOKBACK_DAYS = 30


def _error(msg):
    return False, {'errcode': -1, 'errmsg': msg}


def _no_address(msg):
    return None, {'errcode': -1, 'errmsg': msg}


def _configured_points_transfer_address():
    # POINTS_TRANSFER_ADDRESS in settings.cfg - optional override of the GameHub lookup
    address = getattr(app_config, 'POINTS_TRANSFER_ADDRESS', None)
    return Web3.toChecksumAddress(address) if address else None


def _game_hub(web3eth):
    address = Web3.toChecksumAddress(app_config.CHAINS['binance']['GAME_HUB_ADDRESS'])
    return web3eth._w3.eth.contract(address=address, abi=GAME_HUB_ABI)


def _discover_points_transfers(web3eth):
    # PointsTransfer contracts registered on our GameHub: listed by GameHub.getPointsManagers()
    # and pointing back at the same GameHub via PointsTransfer.hub().
    # returns None when the GameHub has no points-manager support yet (call reverts).
    hub = _game_hub(web3eth)
    try:
        managers = hub.functions.getPointsManagers().call()
    except Exception as e:
        logger.info('GameHub.getPointsManagers() unavailable: {}'.format(e))
        return None
    found = []
    for manager in managers:
        manager = Web3.toChecksumAddress(manager)
        contract = web3eth._w3.eth.contract(address=manager, abi=POINTS_TRANSFER_ABI)
        try:
            if Web3.toChecksumAddress(contract.functions.hub().call()) == hub.address:
                found.append(manager)
        except Exception as e:
            # a points manager that is not a PointsTransfer contract
            logger.info('points manager {} is not a PointsTransfer: {}'.format(manager, e))
    logger.info('GameHub points managers: {}, PointsTransfer: {}'.format(managers, found))
    return found


def get_points_transfer_address(web3eth, requested=None):
    # resolve the PointsTransfer contract to sign for.
    # returns (address, None) or (None, {'errcode': -1, 'errmsg': ...}).
    # POINTS_TRANSFER_ADDRESS set -> use it; empty -> look it up on the GameHub.
    # `requested` (optional, checksummed) picks one when several are registered.
    configured = _configured_points_transfer_address()
    if configured:
        if requested and requested != configured:
            return _no_address('transferContract is not the configured PointsTransfer contract.')
        return configured, None

    candidates = _discover_points_transfers(web3eth)
    if not candidates:
        return _no_address('points transfer contract not available.')
    if requested:
        if requested not in candidates:
            return _no_address('transferContract is not a PointsTransfer registered on the game hub.')
        return requested, None
    if len(candidates) > 1:
        return _no_address('multiple PointsTransfer contracts registered, transferContract is required.')
    return candidates[0], None


def _access_control_address(hub):
    # ACCESS_CONTROL_ADDRESS set -> use it (no chain call); empty -> GameHub.accessControl()
    address = getattr(app_config, 'ACCESS_CONTROL_ADDRESS', None)
    if address:
        return Web3.toChecksumAddress(address)
    return Web3.toChecksumAddress(hub.functions.accessControl().call())


def check_points_addresses(web3eth, source, destination, invoked_by, contract_address):
    try:
        return _check_points_addresses(web3eth, source, destination, invoked_by, contract_address)
    except Exception as e:
        logger.exception('points address check error: {}'.format(e))
        return _error('could not read chain data, please try again later.')


def _check_points_addresses(web3eth, source, destination, invoked_by, contract_address):
    # address safety checks - addresses arrive checksummed from the controller.
    # return (True, None) to allow, or (False, {'errcode': -1, 'errmsg': ...}) to reject.
    # moves points out of a hacked/frozen wallet to its safe wallet (or another wallet on the same
    # safe wallet). mirrors PointsTransfer._checkInstance / _checkSafeWallet so a request the contract
    # would revert is never signed, then applies the frozen-wallet business rules:
    #   1. receiver is the source's safe wallet, or shares the same safe wallet - else reject
    #   2. maxClaimablePoints(receiver) <= maxClaimablePoints(source) - pass, else go to 3
    #   3. carry-forward points over all operators: receiver >= source - pass, else reject
    if source == destination:
        return _error('destination must be different from source.')

    hub = _game_hub(web3eth)
    if hub.functions.instanceToOperator(contract_address).call() == ZERO_ADDRESS:
        return _error('contract is not a registered game hub instance.')

    # ACCESS_CONTROL_ADDRESS in settings.cfg, or the ACL the contract uses - GameHub.accessControl()
    acl_address = _access_control_address(hub)
    if acl_address == ZERO_ADDRESS:
        return _error('access control not set on the game hub.')
    acl = web3eth._w3.eth.contract(address=Web3.toChecksumAddress(acl_address), abi=ACCESS_CONTROL_ABI)
    safe_wallet = Web3.toChecksumAddress(acl.functions.safeWalletOf(source).call())
    logger.info('points sign source: {}, destination: {}, invoked by: {}, safe wallet: {}'
                .format(source, destination, invoked_by, safe_wallet))
    if safe_wallet == ZERO_ADDRESS:
        return _error('source has no safe wallet.')
    # only a hacked/frozen wallet (frozen or blacklisted in the ACL) can have its points moved
    if not acl.functions.isRestricted(source).call():
        return _error('source is not a frozen wallet.')
    if acl.functions.isRestricted(safe_wallet).call() or acl.functions.isSafeWalletRevoked(safe_wallet).call():
        return _error('safe wallet is restricted.')
    # destination is the safe wallet itself, or another address linked to the same safe wallet
    if destination != safe_wallet and Web3.toChecksumAddress(acl.functions.safeWalletOf(destination).call()) != safe_wallet:
        return _error('source and destination are not linked to the same safe wallet.')
    if acl.functions.isBlacklisted(destination).call():
        return _error('destination is restricted.')
    if invoked_by != source and invoked_by != safe_wallet:
        return _error('invokedBy must be the source or its safe wallet.')

    # condition 2: receiver's PR-tier max claimable points must not exceed the frozen wallet's
    pr_data, pr_date = _latest_pr()
    if not pr_data:
        return _error('pr data not ready, try again later.')
    source_max = max_claimable_points(source, pr_data)
    destination_max = max_claimable_points(destination, pr_data)
    logger.info('points sign max claimable (pr.json {}): source {}, destination {}'
                .format(pr_date, source_max, destination_max))
    if destination_max <= source_max:
        return True, None

    # condition 3: receiver's carry-forward points over all operators must be >= the frozen wallet's
    source_cf, destination_cf = carry_forward_points_all_operators(web3eth, hub, [source, destination])
    logger.info('points sign carry forward all operators (wei): source {}, destination {}'
                .format(source_cf, destination_cf))
    if destination_cf >= source_cf:
        return True, None
    return _error('destination has a higher points tier than source and less carry forward points than source.')


def _latest_pr():
    # most recent populated pr.json, starting from yesterday (today's may still be mid-write and
    # differ between nodes) - same lookup calculate_boost_job uses for the tier caps.
    for days_back in range(1, PR_LOOKBACK_DAYS + 1):
        date = time_format(timedeltas={'days': days_back}, opera=-1)[:10]
        file_path = os.path.join(data_dir, date, 'pr.json')
        if not os.path.exists(file_path):
            continue
        with open(file_path, 'r') as f:
            data = json.load(f)
        if data.get('MAINNET'):
            return data, date
    return {}, None


def max_claimable_points(address, pr_data):
    # maxClaimablePoints from BOOST_PR_TIER_CAPS: the tier max_points for the wallet's MAINNET
    # share in pr.json. no share / below the lowest tier -> 0 (not eligible),
    # above every tier -> highest max_points.
    tier_caps = app_config.BOOST_PR_TIER_CAPS
    shares = {addr.lower(): share for addr, share in pr_data.get('MAINNET', {}).items()}
    share = Decimal(str(shares.get(address.lower(), 0)))
    for tier in tier_caps:
        if Decimal(str(tier['min_share'])) <= share < Decimal(str(tier['max_share'])):
            return Decimal(str(tier['max_points']))
    if share < min(Decimal(str(tier['min_share'])) for tier in tier_caps):
        return Decimal(0)
    return max(Decimal(str(tier['max_points'])) for tier in tier_caps)


def carry_forward_points_all_operators(web3eth, hub, addresses):
    # sum of carryForwardPoints (wei, int256) for each address over every GameHub operator instance
    totals = [0] * len(addresses)
    for operator in hub.functions.getOperators().call():
        instance = hub.functions.getInstance(operator).call()
        if instance == ZERO_ADDRESS:
            continue
        contract = web3eth._w3.eth.contract(address=Web3.toChecksumAddress(instance), abi=DAILY_SESSION_MANAGER_ABI)
        for i, address in enumerate(addresses):
            totals[i] += contract.functions.carryForwardPoints(address).call()
    return totals


def check_points_balance(source, points, web3eth, contract_address):
    # return (True, None) to allow, or (False, {'errcode': -1, 'errmsg': ...}) to reject.
    # spendable balance on the instance (today's unfinalized points excluded) - same as the contract
    # TODO: add more points / business checks here.
    instance = web3eth._w3.eth.contract(address=contract_address, abi=DAILY_SESSION_MANAGER_ABI)
    try:
        available = instance.functions.carryForwardPoints(source).call()
    except Exception as e:
        logger.exception('points balance check error: {}'.format(e))
        return _error('could not read chain data, please try again later.')
    logger.info('points sign source: {}, points: {}, available (wei): {}'.format(source, points, available))
    if available < 0 or Web3.toWei(points, 'ether') > available:
        return _error('not enough points.')
    return True, None


def check_points_interval(source):
    user_file = os.path.join(interval_dir, '{}.json'.format(source))
    if not os.path.exists(user_file):
        return True
    with open(user_file, 'r') as rf:
        interval_data = json.load(rf)
    now_timestamp = get_now_timestamp()
    logger.info('points sign source: {}, now timestamp: {}, interval data: {}'
                .format(source, now_timestamp, interval_data))
    return now_timestamp > interval_data['sign_timestamps'] + INTERVAL_SECONDS


def save_points_interval(source, expected_expiration):
    os.makedirs(interval_dir, exist_ok=True)
    user_file = os.path.join(interval_dir, '{}.json'.format(source))
    interval_data = {'sign_timestamps': get_now_timestamp(), 'expected_expiration': expected_expiration}
    with open(user_file, 'w') as wf:
        json.dump(interval_data, wf)
    return True


def get_chain_id(web3eth):
    # always the chain this node's rpc is on - never taken from the request
    return int(web3eth._w3.eth.chain_id)


def get_points_sign(web3eth, transfer_address, source, destination, invoked_by, contract_address, points,
                    expected_expiration, chain_id):
    w3 = web3eth._w3
    contract_instance = w3.eth.contract(address=transfer_address, abi=POINTS_TRANSFER_ABI)
    domain_separator = contract_instance.functions.DOMAIN_SEPARATOR().call()
    nonce = contract_instance.functions.nonce(source).call()
    logger.info('points sign domain separator: {}, nonce: {}'.format(domain_separator.hex(), nonce))
    points_wei = Web3.toWei(points, 'ether')

    encode_data = encode_abi(['address', 'address', 'address', 'address', 'uint256', 'uint256', 'uint256',
                              'uint256'],
                             [source, destination, invoked_by, contract_address, points_wei,
                              expected_expiration, nonce, chain_id])
    encode_data_hash = w3.sha3(encode_data)
    byte_hash = w3.soliditySha3(['bytes1', 'bytes1', 'bytes32', 'bytes32'],
                                ['0x19', '0x01', domain_separator, encode_data_hash])
    byte_str_hash = byte_hash.hex()
    msg = encode_defunct(hexstr=byte_str_hash)
    signed_message = w3.eth.account.sign_message(msg, app_config.WALLET_PRIVATE_KEY)
    return signed_message.signature.hex(), nonce, byte_str_hash, points_wei


def get_points_code(web3eth, source, destination, invoked_by, contract_address, points_wei, expiration, raw_sign):
    # same shape as Web3Eth.get_code, extended with the extra addresses
    w3 = web3eth._w3
    addr_hash = w3.sha3(encode_abi(['address', 'address', 'address', 'address'],
                                   [source, destination, invoked_by, contract_address]))
    unit_hash = w3.sha3(encode_abi(['uint256'], [points_wei - expiration]))
    code = w3.sha3(encode_abi(['bytes32', 'bytes32', 'bytes32'],
                              [addr_hash, unit_hash, bytes.fromhex(raw_sign[2:])])).hex()
    logger.info('points code: {}'.format(code))
    return code


def parse_points(value):
    try:
        points = Decimal(str(value))
    except Exception:
        return None
    # at most 18 decimals (1e18 scaled on-chain)
    if not points.is_finite() or points < MIN_POINTS or points.as_tuple().exponent < -18:
        return None
    return points
