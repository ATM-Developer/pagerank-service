import pytz
import logging
import traceback
from collections import OrderedDict
from datetime import datetime

from project.extensions import app_config
from project.utils.network_util import directed_graph
from project.utils.date_util import get_pagerank_date
from project.utils.reader_util import EthDataReader
from project.utils.cache_util import CacheUtil


class ToCalculate:
    def __init__(self):
        self.cache_util = CacheUtil()
        self.logger = logging.getLogger('calculate')

    # def _cal_pr_coe(self, pr_dict):
    #     sorted_pr = sorted(list(pr_dict.values()))
    #     sub = sorted_pr[:round(len(sorted_pr) / 10)]
    #     if len(sub) == 0:
    #         return 1
    #     else:
    #         div = sum(sub) / len(sub)
    #         return div

    def calculate(self):
        coin_list = self.cache_util.get_today_coin_list()
        coin_info = {}
        for data in coin_list['coinCurrencyPairList']:
            if data['status'] == 1:
                continue
            symbol = data['baseCurrency'].upper()
            if data['chainId'] == 2 and symbol in coin_info:
                continue
            coin_info[symbol] = {
                'coefficient': data['coefficient'],
                'decimals': int(data['weiPlaces']),
                'alone_calculate': int(data['aloneCalculateFlag']),
                'contract_address': data['contractAddress'],
                'alone_reward_amount': int(data['aloneRewardAmount']),
                'net_reward_amount': int(data['netRewardAmount']),
                'chain_id': data['chainId'],
                'gateway': data['gateWay']
            }
        luca_amount = self.cache_util.get_today_luca_amount()
        try:
            link_rate = float(luca_amount['linkUsdRate'])
        except:
            self.logger.error('No link rate data, can not calculate PR, exit')
            return False
        coin_price = self.cache_util.get_today_coin_price()
        # merge coin info list and coin price
        for key, value in coin_info.items():
            if key in coin_price:
                coin_info[key]['price'] = coin_price[key]
            else:
                self.logger.error('No price info for {}, can not calculate PR, exit'.format(key))
                return False
        # prepare date
        pagerank_date = get_pagerank_date()
        date_str = pagerank_date.split('-')
        # deadline is 21 o'clock(UTC)
        deadline_datetime = datetime(int(date_str[0]), int(date_str[1]), int(date_str[2]), app_config.OTHER_HOUR,
                                     app_config.OTHER_MINUTE, tzinfo=pytz.timezone('UTC'))
        contract_deadline_timestamp = int(deadline_datetime.timestamp())
        # prepare block info yesterday
        block_number_yesterday = self.cache_util.get_cache_block_number()
        if block_number_yesterday is None:
            block_number_yesterday = {}
        for chain_name, chain_info in app_config.CHAINS.items():
            if chain_name not in block_number_yesterday:
                block_number_yesterday[chain_name] = chain_info.get('FIRST_BLOCK')
        # prepare contract data
        recorded = []
        unrecorded = []
        last_block_info_today = OrderedDict()
        for chain_name, last_block_number_yesterday in block_number_yesterday.items():
            data_reader = EthDataReader(chain=chain_name, tlogger=self.logger)
            _recorded, _unrecorded, _last_block_number_today = data_reader.prepare_data(
                contract_deadline_timestamp, last_block_number_yesterday)
            recorded.extend(_recorded)
            unrecorded.extend(_unrecorded)
            last_block_info_today[chain_name] = _last_block_number_today
        self.cache_util.save_cache_block_number(last_block_info_today)
        # prepare contract and user from cache
        g = directed_graph(contract_deadline_timestamp, coin_info, link_rate)
        contract_and_user = self.cache_util.get_cache_contract_and_user()
        if contract_and_user is not None:
            g.load_contract_and_user(contract_and_user)
        # remove recorded data which has been rescinded
        g.remove_transactions(recorded)
        # add unrecorded data
        for i in unrecorded:
            g.build_from_new_transaction(i)
        # generate pr results
        add2pr = g.generate_pr()
        # generate individual pr for special coins
        individual_pr = OrderedDict()
        for key, value in coin_info.items():
            if coin_info[key]['alone_calculate'] == 2:
                coin_pr = g.generate_pr_info(key)
                individual_pr[key] = coin_pr
            else:
                pass
        individual_pr['MAINNET'] = add2pr
        # save pr
        self.cache_util.save_cache_pr(individual_pr)
        # prepare pr coe
        # yesterday_pr_coe = self.cache_util.get_cache_pr_coe()
        # today_pr_coe = OrderedDict()
        # for key, value in individual_pr.items():
        #     coe = self._cal_pr_coe(value)
        #     if key in yesterday_pr_coe:
        #         today_coe = float(min(coe, yesterday_pr_coe[key]))
        #     else:
        #         today_coe = coe
        #     today_pr_coe[key] = today_coe
        # # save pr coe
        # self.cache_util.save_cache_pr_coe(today_pr_coe)
        # save contract and user
        contract_and_user_today = g.get_contract_and_user()
        self.cache_util.save_cache_contract_and_user(contract_and_user_today)
        # save input data
        recorded.extend(unrecorded)
        self.cache_util.save_cache_input_data(recorded)
        return True

    def run(self):
        try:
            self.logger.info('Calculating...')
            success = self.calculate()
            if success:
                self.logger.info('Done')
            else:
                self.logger.info('Failed')
        except:
            self.logger.error(traceback.format_exc())
