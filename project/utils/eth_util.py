import os
import time
import traceback
from web3 import Web3
from web3.middleware import geth_poa_middleware
from eth_abi import encode_abi
from eth_account.messages import encode_defunct

from project.extensions import logger, app_config
from project.configs.eth.eth_config import PLEDGE_ABI, FACTORY_ABI, LINK_ABI, IERC20_ABI, INCENTIVE_ABI, LUCA_ABI, \
    POC_ABI, SENATOR_ABI, SNAPSHOOT_ABI, LEDGER_ABI
from project.utils.date_util import get_now_timestamp, get_pagerank_date, datetime_to_timestamp


class Web3Eth:

    def __init__(self, chain='binance') -> None:
        self._connected = False
        config = app_config.CHAINS.get(chain, None)
        if config is None:
            logger.info('Invalid Chain: {}'.format(chain))
            return
        for i in range(10):
            for uri in config['web3_provider_uri']:
                self._w3 = Web3(Web3.HTTPProvider(uri))
                try:
                    if self._w3.isConnected():
                        self._connected = True
                        logger.info('Selected URI: {}'.format(uri))
                        break
                    else:
                        continue
                except Exception as e:
                    logger.error(e)
            if self._connected:
                break
        if not self._connected:
            logger.info('Invalid web3_provider_uri')
            return
        self._w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        self._factory_contract = self._w3.eth.contract(address=config['FACTORY_ADDRESS'], abi=FACTORY_ABI)
        if 'binance' == chain:
            self._pledge_contract = self._w3.eth.contract(address=app_config.PLEDGE_ADDRESS, abi=PLEDGE_ABI)
            self._luca_contract = self._w3.eth.contract(address=app_config.LUCA_ADDRESS, abi=IERC20_ABI)
            self._busd_contract = self._w3.eth.contract(address=app_config.BUSD_ADDRESS, abi=IERC20_ABI)
        self.current_address = app_config.WALLET_ADDRESS
        self.current_private_key = app_config.WALLET_PRIVATE_KEY
        self._w3.eth.default_account = self.current_address
        self.senator_contract = self._w3.eth.contract(address=app_config.SENATOR_ADDRESS, abi=SENATOR_ABI)
        self.poc_contract = self._w3.eth.contract(address=app_config.POC_ADDRESS, abi=POC_ABI)
        self.snapshoot_contract = self._w3.eth.contract(address=app_config.SNAPSHOOT_ADDRESS, abi=SNAPSHOOT_ABI)

    def get_w3(self):
        return self._w3

    def get_top_nodes(self):
        for i in range(3):
            try:
                res = self._pledge_contract.functions.queryNodeRank(start=1, end=app_config.SERVER_NUMBER).call()
                logger.info('top nodes ： {}'.format(res))
                return res
            except:
                logger.error(traceback.format_exc())
                time.sleep(1)
        return None

    def get_factory_link_active_events(self, from_block=0, to_block='latest'):
        events = self._factory_contract.events.LinkActive.getLogs(fromBlock=from_block, toBlock=to_block)
        return events

    def get_factory_link_created_events(self, from_block=0, to_block='latest'):
        events = self._factory_contract.events.LinkCreated.getLogs(fromBlock=from_block, toBlock=to_block)
        return events

    def get_block_by_number(self, block_number):
        for i in range(10):
            try:
                return self._w3.eth.get_block(block_number)
            except Exception as e:
                logger.error(str(e))
        return None

    def _get_link_contract(self, link_address):
        link_contract = self._w3.eth.contract(link_address, abi=LINK_ABI)
        return link_contract

    def get_link_info(self, link_address):
        while True:
            try:
                link_contract = self._get_link_contract(link_address)
                symbol_, token_, userA_, userB_, amountA_, amountB_, percentA_, totalPlan_, lockDays_, startTime_, status_, isAward_ = link_contract.caller.getLinkInfo()
                link_info = LinkInfo(symbol_, token_, userA_, userB_, amountA_, amountB_, percentA_, totalPlan_,
                                     lockDays_,
                                     startTime_, status_, isAward_)
                return link_info
            except:
                logger.error(traceback.format_exc())
                time.sleep(5)

    def get_link_close_info(self, link_address):
        while True:
            try:
                link_contract = self._get_link_contract(link_address)
                closer_, startTime_, expiredTime_, closeTime_, closeReqA_, closeReqB_ = link_contract.caller.getCloseInfo()
                link_close_info = LinkCloseInfo(closer_, startTime_, expiredTime_, closeTime_, closeReqA_, closeReqB_)
                return link_close_info
            except:
                logger.error(traceback.format_exc())
                time.sleep(5)

    def get_luca_price(self):
        luca_balance = self._luca_contract.functions.balanceOf(app_config.BUSD_LUCA_ADDRESS).call()
        busd_balance = self._busd_contract.functions.balanceOf(app_config.BUSD_LUCA_ADDRESS).call()
        return (busd_balance / 10 ** app_config.BUSD_DECIMALS) / (luca_balance / 10 ** app_config.LUCA_DECIMALS)

    def get_latest_block_number(self):
        for i in range(10):
            try:
                return self._w3.eth.block_number
            except Exception as e:
                logger.error(str(e))

    def get_coin_price(self, contract_address, gateway, coin_decimals):
        contract_address = Web3.toChecksumAddress(contract_address)
        gateway = Web3.toChecksumAddress(gateway)
        coin_contract = self._w3.eth.contract(address=gateway, abi=IERC20_ABI)
        coin_balance = coin_contract.functions.balanceOf(contract_address).call()
        busd_balance = self._busd_contract.functions.balanceOf(contract_address).call()
        return (busd_balance / 10 ** app_config.BUSD_DECIMALS) / (coin_balance / 10 ** coin_decimals)

    def get_sign(self, user_address, amount, contract_address, expected_expiration):
        contract_instance = self._w3.eth.contract(address=app_config.INCENTIVE_ADDRESS, abi=INCENTIVE_ABI)
        domain_separator = contract_instance.functions.DOMAIN_SEPARATOR().call()
        nonce = contract_instance.functions.nonce(Web3.toChecksumAddress(user_address)).call()
        ether_amount = Web3.toWei(amount, 'ether')

        encode_data = encode_abi(['address', 'address', 'uint256', 'uint256', 'uint256'],
                                 [user_address, contract_address, ether_amount, expected_expiration, nonce])
        encode_data_hash = self._w3.sha3(encode_data)
        byte_hash = self._w3.soliditySha3(['bytes1', 'bytes1', 'bytes32', 'bytes32'],
                                          ['0x19', '0x01', domain_separator, encode_data_hash])
        byte_str_hash = byte_hash.hex()
        msg = encode_defunct(hexstr=byte_str_hash)
        signed_message = self._w3.eth.account.sign_message(msg, app_config.WALLET_PRIVATE_KEY)
        signed_str = signed_message.signature.hex()
        return signed_str, nonce, byte_str_hash

    def get_last_block_number(self, address, abi):
        contract_instance = self._w3.eth.contract(address=address, abi=abi)
        to_block = contract_instance.web3.eth.block_number
        logger.info('last block number: {}'.format(to_block))
        return to_block

    def get_transfer_events(self, from_block, to_block, contract_address, contract_abi):
        contract_instance = self._w3.eth.contract(address=contract_address, abi=contract_abi)
        events = contract_instance.events.Transfer.getLogs(fromBlock=from_block, toBlock=to_block)
        return events

    def get_pledge_events(self, event, from_block, to_block, address):
        contract_instance = self._w3.eth.contract(address=address, abi=PLEDGE_ABI)
        if event == 'StakeLuca':
            events = contract_instance.events.StakeLuca.getLogs(fromBlock=from_block, toBlock=to_block)
        elif event == 'EndStakeLuca':
            events = contract_instance.events.EndStakeLuca.getLogs(fromBlock=from_block, toBlock=to_block)
        elif event == 'StakeWLuca':
            events = contract_instance.events.StakeWLuca.getLogs(fromBlock=from_block, toBlock=to_block)
        elif event == 'EndStakeWLuca':
            events = contract_instance.events.EndStakeWLuca.getLogs(fromBlock=from_block, toBlock=to_block)
        else:
            events = []
        # logger.info('this event:{}, from: {} to: {}, pledge count:{}'.format(event, from_block, to_block, len(events)))
        return events

    def get_incentive_events(self, from_block, to_block):
        contract_instance = self._w3.eth.contract(address=app_config.INCENTIVE_ADDRESS, abi=INCENTIVE_ABI)
        events = contract_instance.events.WithdrawToken.getLogs(fromBlock=from_block, toBlock=to_block)
        return events

    def fragment2luca(self, amount, is_fromWei=True):
        contract_instance = self._w3.eth.contract(address=app_config.LUCA_ADDRESS, abi=LUCA_ABI)
        luca_amount = contract_instance.functions.fragmentToLuca(amount).call()
        if is_fromWei:
            new_amount = Web3.fromWei(luca_amount, 'ether')
        else:
            new_amount = luca_amount
        return new_amount

    def get_to_wluca_proportion(self, is_fromWei=False):
        amount = 1000000000000000000000000
        new_amount = self.fragment2luca(amount, is_fromWei)
        return new_amount / amount

    def get_transaction_receipt(self, transaction_hash):
        return self._w3.eth.getTransactionReceipt(transaction_hash)

    def get_transaction_coin_address(self, transaction_hash):
        receipt = self.get_transaction_receipt(transaction_hash)
        return receipt['logs'][0]['address']

    def get_all_senators(self):
        senators = []
        for i in range(app_config.SERVER_NUMBER):
            res = self.senator_contract.functions.senators(i).call()
            senators.append(res)
        return senators

    def is_senators(self, address):
        res = self.senator_contract.functions.isSenator(user=address).call()
        return res

    def get_executer(self):
        res = self.senator_contract.functions.getExecuter().call()
        return res

    def is_executer(self):
        if self.current_address == self.get_executer():
            return True
        return False

    def is_senators_or_executer(self):
        if self.is_executer():
            return 'is executer'
        if self.is_senators(self.current_address):
            return 'is senators'
        return None

    def get_latest_snapshoot_proposal(self):
        res = self.snapshoot_contract.functions.latestSnapshootProposal().call()
        return res

    def get_latest_success_snapshoot_proposal(self):
        res = self.snapshoot_contract.functions.latestSuccesSnapshootProposal().call()
        return res

    def send_snapshoot_proposal(self, tlogger, pr_hash, pr_id):
        nonce = self._w3.eth.get_transaction_count(self.current_address)
        gas_est = self.snapshoot_contract.functions.sendSnapshootProposal(_prHash=pr_hash, _prId=pr_id).estimateGas()
        tlogger.info('send proposal gas est: {}'.format(gas_est))
        unicorn_txn = self.snapshoot_contract.functions.sendSnapshootProposal(_prHash=pr_hash, _prId=pr_id) \
            .buildTransaction({
            'chainId': app_config.CHAIN_ID,
            'gas': gas_est + 10000,
            'gasPrice': self._w3.eth.gas_price,
            'nonce': nonce, })
        tlogger.info('nonce: {}, gas est: {}, unicorn txn: {}'.format(nonce, gas_est, unicorn_txn))
        signed_txn = self._w3.eth.account.sign_transaction(unicorn_txn, private_key=self.current_private_key)
        tx_hash = self._w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        txn_hash = self._w3.toHex(self._w3.keccak(signed_txn.rawTransaction))
        tlogger.info('send snapshoot proposal result tx_hash: {}, Transaction Hash: {}'.format(tx_hash, txn_hash))
        return True

    def check_vote(self, start_timestamp):
        latest_snapshoot = self.get_latest_snapshoot_proposal()
        if latest_snapshoot:
            if latest_snapshoot[5] < start_timestamp:
                return None
            if latest_snapshoot[6] == 1:
                if latest_snapshoot[5] > datetime_to_timestamp('{} {}:{}:00'.format(get_pagerank_date(),
                                                                                    app_config.START_HOUR,
                                                                                    app_config.START_MINUTE)):
                    return latest_snapshoot[6]
            return latest_snapshoot[6]
        return None

    def is_resolution(self):
        res = self.snapshoot_contract.functions.isResolution().call()
        return res  # True or False

    def is_outline(self):
        res = self.snapshoot_contract.functions.isOutLine().call()
        return res  # True or False

    def set_vote(self, tlogger, t_or_f):
        for i in range(5):
            try:
                if self.is_resolution():
                    tlogger.info('resolution is ture')
                    return True
                nonce = self._w3.eth.get_transaction_count(self.current_address)
                gas_est = self.snapshoot_contract.functions.vote(t_or_f).estimateGas()
                tlogger.info('set vote gas est: {}'.format(gas_est))
                unicorn_txn = self.snapshoot_contract.functions.vote(t_or_f).buildTransaction({
                    'chainId': app_config.CHAIN_ID,
                    'gas': gas_est * 2,
                    'gasPrice': self._w3.eth.gas_price,
                    'nonce': nonce, })
                signed_txn = self._w3.eth.account.sign_transaction(unicorn_txn, private_key=self.current_private_key)
                tx_hash = self._w3.eth.send_raw_transaction(signed_txn.rawTransaction)
                txn_hash = self._w3.toHex(self._w3.keccak(signed_txn.rawTransaction))
                tlogger.info('set vote result tx_hash: {}, Transaction Hash: {}'.format(tx_hash, txn_hash))
            except Exception as e:
                if 'Reached a consensus' in str(e) or 'multiple voting' in str(e):
                    break
        return True

    def update_senators(self, tlogger):
        nonce = self._w3.eth.get_transaction_count(self.current_address)
        gas_est = self.poc_contract.functions.updateSenator().estimateGas()
        tlogger.info('update senators gas_est: {}'.format(gas_est))
        unicorn_txn = self.poc_contract.functions.updateSenator().buildTransaction({
            'chainId': app_config.CHAIN_ID,
            'gas': gas_est + 10000,
            'gasPrice': self._w3.eth.gas_price,
            'nonce': nonce, })
        signed_txn = self._w3.eth.account.sign_transaction(unicorn_txn, private_key=self.current_private_key)
        tx_hash = self._w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        txn_hash = self._w3.toHex(self._w3.keccak(signed_txn.rawTransaction))
        tlogger.info('update senators result tx_hash: {}, Transaction Hash: {}'.format(tx_hash, txn_hash))
        return True

    def update_executer(self, tlogger):
        nonce = self._w3.eth.get_transaction_count(self.current_address)
        gas_est = self.poc_contract.functions.updateExecuter().estimateGas()
        tlogger.info('update executer gas_est: {}'.format(gas_est))
        unicorn_txn = self.poc_contract.functions.updateExecuter().buildTransaction({
            'chainId': app_config.CHAIN_ID,
            'gas': gas_est + 10000,
            'gasPrice': self._w3.eth.gas_price,
            'nonce': nonce, })
        signed_txn = self._w3.eth.account.sign_transaction(unicorn_txn, private_key=self.current_private_key)
        tx_hash = self._w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        txn_hash = self._w3.toHex(self._w3.keccak(signed_txn.rawTransaction))
        tlogger.info('update executer result tx_hash: {}, Transaction Hash: {}'.format(tx_hash, txn_hash))
        return True

    def send_forced_change_executer_proposal(self, tlogger):
        try:
            tlogger.info('send forced change executer proposal.')
            nonce = self._w3.eth.get_transaction_count(self.current_address)
            gas_est = self.poc_contract.functions.sendForcedChangeExecuterProposal().estimateGas()
            tlogger.info('send update executer proposal gas est: {}'.format(gas_est))
            unicorn_txn = self.poc_contract.functions.sendForcedChangeExecuterProposal().buildTransaction({
                'chainId': app_config.CHAIN_ID,
                'gas': gas_est + 10000,
                'gasPrice': self._w3.eth.gas_price,
                'nonce': nonce, })
            tlogger.info('nonce: {}, gas est: {}, unicorn txn: {}'.format(nonce, gas_est, unicorn_txn))
            signed_txn = self._w3.eth.account.sign_transaction(unicorn_txn, private_key=self.current_private_key)
            tx_hash = self._w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            txn_hash = self._w3.toHex(self._w3.keccak(signed_txn.rawTransaction))
            tlogger.info('send update executer snapshoot proposal result tx_hash: {}, Transaction Hash: {}'
                         .format(tx_hash, txn_hash))
            return True
        except Exception as e:
            tlogger.error(traceback.format_exc())
            if 'The latest proposal has no resolution' in str(e):
                return 'latest proposal has no resolution'
        return False

    def set_vote_update_executer_proposal(self, tlogger, t_or_f):
        for i in range(5):
            try:
                if self.poc_contract.functions.isResolution().call():
                    tlogger.info('resolution is ture')
                    return True
                nonce = self._w3.eth.get_transaction_count(self.current_address)
                gas_est = self.poc_contract.functions.vote(t_or_f).estimateGas()
                tlogger.info('set update executer proposal vote gas est: {}'.format(gas_est))
                unicorn_txn = self.poc_contract.functions.vote(t_or_f).buildTransaction({
                    'chainId': app_config.CHAIN_ID,
                    'gas': gas_est * 2,
                    'gasPrice': self._w3.eth.gas_price,
                    'nonce': nonce, })
                signed_txn = self._w3.eth.account.sign_transaction(unicorn_txn, private_key=self.current_private_key)
                tx_hash = self._w3.eth.send_raw_transaction(signed_txn.rawTransaction)
                txn_hash = self._w3.toHex(self._w3.keccak(signed_txn.rawTransaction))
                tlogger.info('set vote result tx_hash: {}, Transaction Hash: {}'.format(tx_hash, txn_hash))
            except Exception as e:
                if 'Reached a consensus' in str(e) or 'multiple voting' in str(e):
                    break
        return True

    def get_epochid(self):
        res = self.senator_contract.functions.epochId().call()
        return res

    def get_snapshoots(self, epochid):
        res = self.snapshoot_contract.functions.snapshoots(epochid).call()
        return res

    def get_executer_id(self):
        res = self.senator_contract.functions.executerId().call()
        return res

    def get_executer_indate(self):
        res = self.senator_contract.functions.executerIndate().call()
        return res

    def is_violation(self, start_timestamp):
        now_timestamp = get_now_timestamp()
        if now_timestamp > self.get_executer_indate():
            return True
        if self.is_outline():
            return True
        latest_proposal = self.get_latest_snapshoot_proposal()
        if latest_proposal[5] > start_timestamp and latest_proposal[-1] == 2:
            return True
        return False

    def is_violation2(self, now_executer, today_timestamp):
        latest_proposal = self.get_latest_snapshoot_proposal()
        if latest_proposal[5] < today_timestamp and latest_proposal[-1] == 1 and latest_proposal[-3] == now_executer:
            return True
        return False


class LinkInfo:

    def __init__(self, symbol_, token_, userA_, userB_, amountA_, amountB_, percentA_, totalPlan_, lockDays_,
                 startTime_, status_, isAward_):
        self.symbol_ = symbol_
        self.token_ = token_
        self.userA_ = userA_
        self.userB_ = userB_
        self.amountA_ = amountA_
        self.amountB_ = amountB_
        self.percentA_ = percentA_
        self.totalPlan_ = totalPlan_
        self.lockDays_ = lockDays_
        self.startTime_ = startTime_
        self.status_ = status_
        self.isAward_ = isAward_


class LinkCloseInfo:

    def __init__(self, closer_, startTime_, expiredTime_, closeTime_, closeReqA_, closeReqB_):
        self.closer_ = closer_
        self.startTime_ = startTime_
        self.expiredTime_ = expiredTime_
        self.closeTime_ = closeTime_
        self.closeReqA_ = closeReqA_
        self.closeReqB_ = closeReqB_


def check_vote(web3eth, tlogger, start_timestamp, flag_file_path=None, now_executer=None):
    tlogger.info('wait check vote..')
    start_time = get_now_timestamp()
    while True:
        try:
            result = web3eth.check_vote(start_timestamp)
            if result == 1:
                tlogger.info('check vote ok')
                return True
            elif result == 2:
                tlogger.info('the vote failed. again')
                break
            if now_executer and now_executer != web3eth.get_executer():
                break
        except:
            pass
        if flag_file_path and not os.path.exists(flag_file_path):
            break
        if get_now_timestamp() - start_time > app_config.VOTE_EPOCH * 60:
            tlogger.info('time > {}min, check vote failed.'.format(app_config.VOTE_EPOCH))
            break
        time.sleep(1)
    return False


class PrivateChain2():

    def __init__(self):
        self._url = app_config.PRIVATE_CHAIN_URL
        self._chain_id = app_config.PRIVATE_CHAIN_ID
        self.default_account = app_config.WALLET_ADDRESS
        self.default_private_key = app_config.WALLET_PRIVATE_KEY
        self._connected = False
        for i in range(10):
            for uri in self._url:
                self.w3 = Web3(Web3.HTTPProvider(uri))
                try:
                    if self.w3.isConnected():
                        self._connected = True
                        logger.info('Selected URI: {}'.format(uri))
                        break
                    else:
                        continue
                except Exception as e:
                    logger.error(e)
            if self._connected:
                break
        self.w3.eth.default_account = self.default_account
        self.ledger_contract = self.w3.eth.contract(address=app_config.LEDGER_ADDRESS, abi=LEDGER_ABI)

    def is_node_addr(self):
        return self.ledger_contract.functions.nodeAddrSta(self.default_account).call()

    def get_node_addresses(self):
        return self.ledger_contract.functions.queryNodes().call()

    def query_vote_result(self, addr, nonce):
        res = self.ledger_contract.functions.queryVotes(Web3.toChecksumAddress(addr), nonce).call()
        return res[0]

    def update_nodes(self, addrs, tlogger):
        update_fun = self.ledger_contract.functions.updateNodes
        # update_fun = self.ledger_contract.functions.testUpdateNodes
        nonce = self.w3.eth.get_transaction_count(self.default_account)
        gas_est = update_fun(addrs).estimateGas()
        unicorn_txn = update_fun(addrs).buildTransaction({
            'chainId': self._chain_id,
            'gas': gas_est + 30000,
            'gasPrice': self.w3.eth.gas_price,
            'nonce': nonce, })
        tlogger.info('need gas: {}'.format(unicorn_txn))
        signed_txn = self.w3.eth.account.sign_transaction(unicorn_txn, private_key=self.default_private_key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        txn_hash = self.w3.toHex(self.w3.keccak(signed_txn.rawTransaction))
        tlogger.info('tx_hash: {}, Transaction Hash: {}'.format(tx_hash, txn_hash))

    def test_update_nodes(self, addrs):
        return self.ledger_contract.functions.testUpdateNodes(addrs).call()

    def __reset_amount(self, amount):
        if '.' in amount:
            str1, str2 = amount.split('.')
        else:
            str1 = amount
            str2 = ''
        return int('{}{}'.format(str1, str2 + '0' * (app_config.EARNINGS_ACCURACY - len(str2))))

    def update_ledgers(self, items, tlogger):
        if not items:
            return True
        _userAddrs, _nonces, _tokenAddrs, _amounts, _txhashs = [], [], [], [], []
        for i in items:
            tlogger.info('{}'.format(i))
            _userAddrs.append(Web3.toChecksumAddress(i['address']))
            _nonces.append(i['nonce'])
            _tokenAddrs.append(i['coin_address'])
            _amounts.append(self.__reset_amount(i['amount']))
            _txhashs.append(i['hash_value'])
        nonce = self.w3.eth.get_transaction_count(self.default_account)
        gas_est = self.ledger_contract.functions.updateLedger(_userAddrs=_userAddrs,
                                                              _nonces=_nonces,
                                                              _tokenAddrs=_tokenAddrs,
                                                              _amounts=_amounts,
                                                              _txHashs=_txhashs).estimateGas()
        tlogger.info('need gas: {}'.format(gas_est))
        unicorn_txn = self.ledger_contract.functions.updateLedger(_userAddrs=_userAddrs, _nonces=_nonces,
                                                                  _tokenAddrs=_tokenAddrs, _amounts=_amounts,
                                                                  _txHashs=_txhashs) \
            .buildTransaction({
            'chainId': self._chain_id,
            'gas': gas_est * 2,
            'gasPrice': self.w3.eth.gas_price,
            'nonce': nonce})
        signed_txn = self.w3.eth.account.sign_transaction(unicorn_txn, private_key=self.default_private_key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        txn_hash = self.w3.toHex(self.w3.keccak(signed_txn.rawTransaction))
        tlogger.info('tx_hash: {}, Transaction Hash: {}'.format(tx_hash, txn_hash))
        return True

    def get_latest_block_number(self):
        return self.ledger_contract.web3.eth.block_number - 6

    def base_get_events(self, event_name, tlogger, start_block_num=0, end_block_number=0, nums=None):
        interval = -50000
        if event_name == 'UpdateLedger':
            event_func = self.ledger_contract.events.UpdateLedger
        elif event_name == 'UpdateNodeAddr':
            event_func = self.ledger_contract.events.UpdateNodeAddr
        items = []
        for i in range(end_block_number, start_block_num - 1, interval):
            from_block = i + interval + 1 if i + interval + 1 > start_block_num else start_block_num
            to_block = i
            tlogger.info('from {} to {}'.format(from_block, to_block))

            while True:
                try:
                    events = event_func.getLogs(fromBlock=from_block, toBlock=to_block)
                    break
                except:
                    pass
            tlogger.info('events len: {}'.format(len(events)))
            items.extend(events)
            if nums and len(items) > nums:
                break
        return items[:nums] if nums else items

    # error
    def get_block_by_number(self, block_number):
        block = self.w3.eth.get_block(block_number)
        return block
