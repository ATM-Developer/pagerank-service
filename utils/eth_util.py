from web3 import Web3

from Configs.eth.eth_config import PLEDGE_ABI, PLEDGE_ADDRESS


class Web3Eth():

    def __init__(self, infura_url) -> None:
        # 初始化客户端
        self.w3 = Web3(Web3.HTTPProvider(infura_url))

    # 查询top11
    def get_top11(self):
        contract_instance = self.w3.eth.contract(address=PLEDGE_ADDRESS, abi=PLEDGE_ABI)
        res = contract_instance.functions.queryNodeRank(start=1, end=11).call()
        print("top11： {}".format(res))
        return res
