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
from project.utils.nft_reader_util import NftDataReader


class ToCalculate:
    def __init__(self):
        self.cache_util = CacheUtil()
        self.logger = logging.getLogger('calculate')

    def calculate(self):
        coin_list = self.cache_util.get_today_coin_list()
        coin_info = {}
        for data in coin_list['coinCurrencyPairList']['pre']:
            if data['status'] != 2:
                continue
            symbol = data['baseCurrency'].upper()
            if symbol in coin_info:
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
        try:
            nft_cap = float(luca_amount['NftValueCap'])
        except:
            self.logger.error('No NFT Value Cap data, can not calculate PR, exit')
            return False
        coin_price = self.cache_util.get_today_coin_price()
        # merge coin info list and coin price
        for key, value in coin_info.items():
            if key in coin_price:
                coin_info[key]['price'] = coin_price[key]
            else:
                self.logger.error('No price info for {}, can not calculate PR, exit'.format(key))
                return False
        nft_info = {}
        for data in coin_list['coinCurrencyPairList']['nft']:
            address = data['address']
            nft_info[address] = {
                'symbol': data['symbol'],
                'coefficient': data.get('coefficient', 1),
                'price': coin_price['nft_{}'.format(address)]
            }
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
            if chain_name not in block_number_yesterday and chain_info:
                block_number_yesterday[chain_name] = chain_info.get('FIRST_BLOCK')
        block_number_yesterday = {k: v for k, v in block_number_yesterday.items() if app_config.CHAINS.get(k)}
        nft_block_number_yesterday = self.cache_util.get_cache_nft_block_number()
        if nft_block_number_yesterday is None:
            nft_block_number_yesterday = {}
        for chain_name, chain_info in app_config.CHAINS.items():
            if 'NFT_FIRST_BLOCK' in chain_info:
                if chain_name not in nft_block_number_yesterday:
                    nft_block_number_yesterday[chain_name] = chain_info.get('NFT_FIRST_BLOCK')
        nft_block_number_yesterday = {k: v for k, v in nft_block_number_yesterday.items() if app_config.CHAINS.get(k)}
        # prepare contract data
        recorded = []
        unrecorded = []
        # coin contracts
        last_block_info_today = OrderedDict()
        for chain_name, last_block_number_yesterday in block_number_yesterday.items():
            data_reader = EthDataReader(chain=chain_name, tlogger=self.logger)
            _recorded, _unrecorded, _last_block_number_today = data_reader.prepare_data(
                contract_deadline_timestamp, last_block_number_yesterday)
            recorded.extend(_recorded)
            unrecorded.extend(_unrecorded)
            last_block_info_today[chain_name] = _last_block_number_today
        self.cache_util.save_cache_block_number(last_block_info_today)
        # nft contracts
        nft_last_block_info_today = OrderedDict()
        for chain_name, last_block_number_yesterday in nft_block_number_yesterday.items():
            data_reader = NftDataReader(chain=chain_name, tlogger=self.logger)
            _recorded, _unrecorded, _last_block_number_today = data_reader.prepare_data(
                contract_deadline_timestamp, last_block_number_yesterday)
            recorded.extend(_recorded)
            unrecorded.extend(_unrecorded)
            nft_last_block_info_today[chain_name] = _last_block_number_today
        self.cache_util.save_cache_nft_block_number(nft_last_block_info_today)
        # prepare contract and user from cache
        g = directed_graph(contract_deadline_timestamp, coin_info, link_rate, nft_info, nft_cap)
        contract_and_user = self.cache_util.get_cache_contract_and_user()
        if contract_and_user is not None:
            g.load_contract_and_user(contract_and_user)
        # add unrecorded data
        for i in unrecorded:
            g.build_from_new_transaction(i)
        # remove recorded data which has been rescinded
        g.remove_transactions(recorded)
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

        # calculate agf pr 
        self.calculate_agf_pr(individual_pr)

        # save contract and user
        contract_and_user_today = g.get_contract_and_user()
        self.cache_util.save_cache_contract_and_user(contract_and_user_today)
        # save input data
        recorded.extend(unrecorded)
        self.cache_util.save_cache_input_data(recorded)
        return True

    def calculate_agf_pr(self, individual_pr):
        try:
            self.logger.info('Calculating... AGF')
            agf_multiplier_list = self.cache_util.get_today_agf_multiplier()
            multiplier_dict = {item['address'].lower(): item['pr_multiplier'] for item in agf_multiplier_list}
            total_old_value = 0
            total_new_value = 0
            total_after_normalization = 0
            if not agf_multiplier_list:
                self.logger.info("AGF multiplier list is empty. so PR is unchanged ")

            for address in individual_pr['MAINNET']:
                addr_lc = address.lower()
                old_value = individual_pr['MAINNET'][address]
                total_old_value += old_value
                multiplier = multiplier_dict.get(addr_lc, 1)
                if multiplier > 1.5:
                    self.logger.warning(f"Multiplier > 1.5 for address {address}: {multiplier}. Capping to 1.")
                    multiplier = 1
                new_value = old_value * multiplier
                total_new_value += new_value
                individual_pr['MAINNET'][address] = new_value

            self.cache_util.save_cache_pr_agf(individual_pr)
            # Normalize so the total sum matches the original total
            if total_new_value != 0:
                normalization_factor = total_old_value / total_new_value
                for address in individual_pr['MAINNET']:
                    individual_pr['MAINNET'][address] *= normalization_factor
                self.logger.info(f"Applied normalization factor: {normalization_factor}")
            else:
                self.logger.warning("Total new value is zero, skipping normalization.")

            
            for address in individual_pr['MAINNET']:
                addr_lc = address.lower()
                tmp_value = individual_pr['MAINNET'][address]
                total_after_normalization += tmp_value
 

            self.logger.info(f'calculate_agf_pr Total old value: {total_old_value}, Total new sum value: {total_new_value} and  Total after normalization: {total_after_normalization}')
            self.cache_util.save_cache_pr_agf_normalize(individual_pr)
            return True
        except Exception as e:
            self.logger.info(f"Error in calculate_agf_pr: {e}")
            return False

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
            raise
