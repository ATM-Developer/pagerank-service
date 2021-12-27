from web3 import Web3
from web3.middleware import geth_poa_middleware
from Configs.eth.eth_config import PLEDGE_ABI, FACTORY_ABI, LINK_ABI, IERC20_ABI
from utils.config_util import params
import traceback
import time


class Web3Eth:

    def __init__(self) -> None:
        self._connected = False
        for uri in params.web3_provider_uri:
            self._w3 = Web3(Web3.HTTPProvider(uri))
            if self._w3.isConnected():
                self._connected = True
                print('Selected URI: {}'.format(uri))
                break
            else:
                continue
        if not self._connected:
            print('Invalid web3_provider_uri')
            return
        self._w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        self._pledge_contract = self._w3.eth.contract(address=params.PLEDGE_ADDRESS, abi=PLEDGE_ABI)
        self._factory_contract = self._w3.eth.contract(address=params.FACTORY_ADDRESS, abi=FACTORY_ABI)
        self._luca_contract = self._w3.eth.contract(address=params.LUCA_ADDRESS, abi=IERC20_ABI)
        self._busd_contract = self._w3.eth.contract(address=params.BUSD_ADDRESS, abi=IERC20_ABI)

    def get_w3(self):
        return self._w3

    def get_top11(self):
        res = self._pledge_contract.functions.queryNodeRank(start=1, end=11).call()
        print("top11： {}".format(res))
        return res

    def get_factory_link_active_events(self, from_block=0, to_block='latest'):
        events = self._factory_contract.events.LinkActive.getLogs(fromBlock=from_block, toBlock=to_block)
        return events

    def get_factory_link_created_events(self, from_block=0, to_block='latest'):
        events = self._factory_contract.events.LinkCreated.getLogs(fromBlock=from_block, toBlock=to_block)
        return events

    def get_block_by_number(self, block_number):
        block = self._w3.eth.get_block(block_number)
        return block

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
                print(traceback.format_exc())
                time.sleep(5)

    def get_link_close_info(self, link_address):
        while True:
            try:
                link_contract = self._get_link_contract(link_address)
                closer_, startTime_, expiredTime_, closeTime_, closeReqA_, closeReqB_ = link_contract.caller.getCloseInfo()
                link_close_info = LinkCloseInfo(closer_, startTime_, expiredTime_, closeTime_, closeReqA_, closeReqB_)
                return link_close_info
            except:
                print(traceback.format_exc())
                time.sleep(5)

    def get_luca_price(self):
        luca_balance = self._luca_contract.functions.balanceOf(params.BUSD_LUCA_ADDRESS).call()
        busd_balance = self._busd_contract.functions.balanceOf(params.BUSD_LUCA_ADDRESS).call()
        return (busd_balance / 10 ** params.BUSD_DECIMALS) / (luca_balance / 10 ** params.LUCA_DECIMALS)

    def get_latest_block_number(self):
        return self._w3.eth.block_number

    def get_coin_price(self, contract_address, gateway, coin_decimals):
        contract_address = Web3.toChecksumAddress(contract_address)
        gateway = Web3.toChecksumAddress(gateway)
        coin_contract = self._w3.eth.contract(address=gateway, abi=IERC20_ABI)
        coin_balance = coin_contract.functions.balanceOf(contract_address).call()
        busd_balance = self._busd_contract.functions.balanceOf(contract_address).call()
        return (busd_balance / 10 ** params.BUSD_DECIMALS) / (coin_balance / 10 ** coin_decimals)


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
