import os
import json
import pickle
import shutil
from decimal import Decimal, getcontext
from collections import OrderedDict
from project.utils.settings_util import get_cfg
from project.utils.date_util import get_pagerank_date, get_previous_pagerank_date, time_format
from project.extensions import  app_config
import requests
import time
from project.utils.cipher import decrypt_file_inplace



class CacheUtil:
    _COIN_LIST_FILE_NAME = 'coin_list.json'
    _LUCA_AMOUNT_FILE_NAME = 'luca_amount.json'
    _DAY_AMOUNT_FILE_NAME = 'day_amount.json'
    _COIN_PRICE_FILE_NAME = 'coin_price.json'
    _COIN_PRICE_TEMP_FILE_NAME = 'coin_price_temp.json'
    _BLOCK_NUMBER_FILE_NAME = 'block_number.json'
    _NFT_BLOCK_NUMBER_FILE_NAME = 'nft_block_number.json'
    _CONTRACT_AND_USER_FILE_NAME = 'contract_and_user.pickle'
    _PR_FILE_NAME = 'pr.json'
    _INPUT_DATA_FILE_NAME = 'input_data.pickle'
    # _PR_COE_FILE_NAME = 'pr_coe.json'

    _PLEDGE_DATAS_FILE_NAME = 'pledge_datas.json'
    _LIQUIDITY_DATAS_FILE_NAME = 'liquidity_datas.json'
    _LIQUIDITY_PERCENTAGE_DATAS_FILE_NAME = 'liquidity_percentage.json'
    _PLEDGE_BLOCK_NUMBER_FILE_NAME = 'pledge_block_number.json'
    _LIQUIDITY_BLOCK_NUMBER_FILE_NAME = 'liquidity_block_number.json'
    _PRIVATE_PLACEMENT_LIQUIDITY_FILE_NAME = 'private_placement_liquidity.json'
    _PREFETCHING_EVENT_BLOCK_NUMBER_FILE_NAME = 'prefetching_event_block_number.json'
    _EARNINGS_TOP_NODES_DATAS_FILE_NAME = 'earnings_top_nodes.json'
    _EARNINGS_PLEDGE_DATAS_FILE_NAME = 'earnings_pledge.json'
    _EARNINGS_LIQUIDITY_DATAS_FILE_NAME = 'earnings_liquidity.json'
    _EARNINGS_MAIN_PR_DATAS_FILE_NAME = 'earnings_main_pr.json'
    _EARNINGS_NET_PR_DATAS_FILE_NAME = 'earnings_net_pr.json'
    _EARNINGS_ALONE_PR_DATAS_FILE_NAME = 'earnings_alone_pr.json'
    _TOP_NODES_FILE_NAME = 'top_nodes.json'
    _USER_TOTAL_EARNINGS_DIR = 'total_earnings'
    _SENATORS_FILE_NAME = 'senators.json'

    _CC_PR_FILE_NAME = 'cc_pr.json'
    _AGF_PR_FILE_NAME = 'agf_pr.json'
    _AGF_MULTIPLIER_NAME = 'agf_multiplier.json'
    _AGF_PR_FILE_NAME_NM = 'agf_pr_normalize.json'

    _BOOST_MEMORY_FILE_NAME = 'boost_memory.json'
    _BOOST_PR_FILE_NAME = 'boost_pr.json'
    _BOOST_REWARD_FILE_NAME = 'boost_reward.json'
    _BOOST_PR_SOURCE_FILE_NAME = 'boost_pr_source.json'

    # Names the boost jobs write directly into <date>-boost themselves (via
    # _boost_output_dir()/save_boost_day_amount/save_boost_luca_amount) -
    # _dual_write_paths must never also write the main folder's pristine
    # version here, or it would clobber the boost-carved value right after
    # the boost job wrote it.
    _BOOST_SYNC_EXCLUDE = {
        _BOOST_PR_FILE_NAME, _BOOST_REWARD_FILE_NAME, _BOOST_PR_SOURCE_FILE_NAME,
        _DAY_AMOUNT_FILE_NAME, _LUCA_AMOUNT_FILE_NAME,
    }

    def _dual_write_paths(self, filename):
        """Returns the full path(s) `filename` should be written to: just
        _cache_full_path normally, plus _boost_output_dir() too when
        BOOST_DATA_DIR is True and filename isn't one of the boost-specific
        names in _BOOST_SYNC_EXCLUDE (those get their own deliberately
        different value written straight to _boost_output_dir() elsewhere -
        dual-writing here would stomp that carved value with the pristine
        one). This replaces the old _sync_boost_output() snapshot-copy
        approach for individual files with a direct write-time flag check,
        so the boost folder is always exactly current instead of frozen at
        whatever existed the last time a CacheUtil() happened to be
        constructed. When BOOST_DATA_DIR is False, _boost_output_dir()
        resolves to _cache_full_path itself, so the two paths collapse to
        one and this is a no-op difference from writing directly - flipping
        the flag either way never changes what gets written, only whether
        it also lands in a second folder."""
        paths = [os.path.join(self._cache_full_path, filename)]
        if getattr(app_config, 'BOOST_DATA_DIR', False) and filename not in self._BOOST_SYNC_EXCLUDE:
            boost_path = os.path.join(self._boost_output_dir(), filename)
            if boost_path not in paths:
                paths.append(boost_path)
        return paths

    def __init__(self, date_type='pagerank', hour=None, minute=None):
        """

        :param date_type: pagerank, the date of PageRank Calculating
                          time, UTC date
        :param hour: overrides the pagerank cutoff hour (defaults to
                     START_HOUR) - pass BOOST_START_HOUR for boost jobs, whose
                     own daily cutoff runs earlier than the main PR job's
        :param minute: overrides the pagerank cutoff minute, paired with hour
        """
        self._cache_path = get_cfg('setting', 'data_dir', path_join=True)
        self._cache_date = get_pagerank_date(hour, minute) if date_type == 'pagerank' else time_format()[:10]
        if date_type == 'pagerank':
            self._yesterday_cache_date = get_previous_pagerank_date(hour, minute)
        else:
            self._yesterday_cache_date = time_format(timedeltas={'days': 1}, opera=-1)[:10]
        self._cache_full_path = os.path.join(self._cache_path, self._cache_date)
        self._yesterday_cache_full_path = os.path.join(self._cache_path, self._yesterday_cache_date)
        if not os.path.exists(self._cache_full_path):
            os.mkdir(self._cache_full_path)
        # if os.path.exists(self._yesterday_cache_full_path):
        #     shutil.rmtree(self._yesterday_cache_full_path)
        if not os.path.exists(self._yesterday_cache_full_path):
            os.mkdir(self._yesterday_cache_full_path)

    def save_cache_coin_list(self, coin_list):
        for path in self._dual_write_paths(self._COIN_LIST_FILE_NAME):
            with open(path, 'w') as f:
                json.dump(coin_list, f)

    def get_cache_coin_list(self):
        cache_file_full_path = os.path.join(self._yesterday_cache_full_path, self._COIN_LIST_FILE_NAME)
        # if not os.path.exists(cache_file_full_path):
        #     if not self.get_yesterday_cache():
        #         return None
        with open(cache_file_full_path, 'r') as f:
            data = json.load(f)
            return data

    def get_today_coin_list(self):
        file_full_path = os.path.join(self._cache_full_path, self._COIN_LIST_FILE_NAME)
        with open(file_full_path, 'r') as f:
            data = json.load(f)
            return data

    def save_cache_luca_amount(self, luca_amount):
        luca_amount = OrderedDict(sorted(luca_amount.items(), key=lambda a: a[0]))
        with open(os.path.join(self._cache_full_path, self._LUCA_AMOUNT_FILE_NAME), 'w') as f:
            json.dump(luca_amount, f)

    def get_cache_luca_amount(self):
        cache_file_full_path = os.path.join(self._yesterday_cache_full_path, self._LUCA_AMOUNT_FILE_NAME)
        # if not os.path.exists(cache_file_full_path):
        #     if not self.get_yesterday_cache():
        #         return None
        with open(cache_file_full_path, 'r') as f:
            data = json.load(f)
            return data

    def save_boost_luca_amount(self, luca_amount):
        """Mirrors save_boost_day_amount's pattern: _carve_out_boost_reward
        subtracts boost_reward out of day_amount.json's pr_reward, and
        luca_amount.json's prReward is what pr_reward was originally derived
        from (see coin_util.day_amount) - so it has to carry the same
        carved-down value or the two files silently disagree. Always
        recomputed fresh from get_today_luca_amount()'s pristine main-folder
        value (not reversed/restored like day_amount's carve), since that
        source is never itself mutated while BOOST_DATA_DIR is True."""
        luca_amount = OrderedDict(sorted(luca_amount.items(), key=lambda a: a[0]))
        with open(os.path.join(self._boost_output_dir(), self._LUCA_AMOUNT_FILE_NAME), 'w') as f:
            json.dump(luca_amount, f)

    def get_today_luca_amount(self):
        file_full_path = os.path.join(self._cache_full_path, self._LUCA_AMOUNT_FILE_NAME)
        with open(file_full_path, 'r') as f:
            data = json.load(f)
            return data

    def save_cache_day_amount(self, day_amount):
        day_amount = OrderedDict(sorted(day_amount.items(), key=lambda a: a[0]))
        for k, v in day_amount.items():
            day_amount[k] = str(v)
        with open(os.path.join(self._cache_full_path, self._DAY_AMOUNT_FILE_NAME), 'w') as f:
            json.dump(day_amount, f)

    def save_boost_day_amount(self, day_amount):
        """Same shape as save_cache_day_amount, but for calculate_boost_job's
        boost_reward carve-out specifically: writes to _boost_output_dir()
        instead of unconditionally self._cache_full_path, so the carve
        (which subtracts boost_reward out of pr_reward) lands in the
        isolated <date>-boost folder while BOOST_DATA_DIR is True, and only
        starts mutating the live day_amount.json once that's switched off
        (_boost_output_dir() then resolves to the same path) - config-only
        switch, no code change in calculate_boost_job needed either way."""
        day_amount = OrderedDict(sorted(day_amount.items(), key=lambda a: a[0]))
        for k, v in day_amount.items():
            day_amount[k] = str(v)
        with open(os.path.join(self._boost_output_dir(), self._DAY_AMOUNT_FILE_NAME), 'w') as f:
            json.dump(day_amount, f)

    def get_today_day_amount(self):
        getcontext().prec = 100
        file_full_path = os.path.join(self._cache_full_path, self._DAY_AMOUNT_FILE_NAME)
        with open(file_full_path, 'r') as f:
            data = json.load(f)
            for k, v in data.items():
                data[k] = Decimal(str(v))
            return data

    def get_today_boost_day_amount(self):
        """Same as get_today_day_amount, but reads the boost_reward carve-out
        wherever it actually lives - _boost_output_dir(), not
        self._cache_full_path - so reward_boost_pr_job sees the carved
        pr_reward/boost_reward while BOOST_DATA_DIR is True (isolated) too,
        not just once it's False and the two paths converge."""
        getcontext().prec = 100
        file_full_path = os.path.join(self._boost_output_dir(), self._DAY_AMOUNT_FILE_NAME)
        with open(file_full_path, 'r') as f:
            data = json.load(f)
            for k, v in data.items():
                data[k] = Decimal(str(v))
            return data

    def save_cache_coin_price(self, coin_price):
        coin_price = OrderedDict(sorted(coin_price.items(), key=lambda a: a[0]))
        for path in self._dual_write_paths(self._COIN_PRICE_FILE_NAME):
            with open(path, 'w') as f:
                json.dump(coin_price, f)

    def get_cache_coin_price(self):
        cache_file_full_path = os.path.join(self._yesterday_cache_full_path, self._COIN_PRICE_FILE_NAME)
        # if not os.path.exists(cache_file_full_path):
        #     if not self.get_yesterday_cache():
        #         return None
        with open(cache_file_full_path, 'r') as f:
            data = json.load(f)
            return data

    def get_today_coin_price(self):
        file_full_path = os.path.join(self._cache_full_path, self._COIN_PRICE_FILE_NAME)
        with open(file_full_path, 'r') as f:
            data = json.load(f)
            return data

    def save_cache_coin_price_temp(self, coin_price):
        coin_price = OrderedDict(sorted(coin_price.items(), key=lambda a: a[0]))
        for path in self._dual_write_paths(self._COIN_PRICE_TEMP_FILE_NAME):
            with open(path, 'w') as f:
                json.dump(coin_price, f)

    def get_today_coin_price_temp(self):
        file_full_path = os.path.join(self._cache_full_path, self._COIN_PRICE_TEMP_FILE_NAME)
        with open(file_full_path, 'r') as f:
            data = json.load(f)
            return data

    def save_cache_block_number(self, block_number):
        block_number = OrderedDict(sorted(block_number.items(), key=lambda a: a[0]))
        for path in self._dual_write_paths(self._BLOCK_NUMBER_FILE_NAME):
            with open(path, 'w') as f:
                json.dump(block_number, f)

    def get_cache_block_number(self):
        cache_file_full_path = os.path.join(self._yesterday_cache_full_path, self._BLOCK_NUMBER_FILE_NAME)
        # if not os.path.exists(cache_file_full_path):
        #     if not self.get_yesterday_cache():
        #         return None
        if not os.path.exists(cache_file_full_path):
            return None
        with open(cache_file_full_path, 'r') as f:
            data = json.load(f)
            return data

    def save_cache_nft_block_number(self, block_number):
        block_number = OrderedDict(sorted(block_number.items(), key=lambda a: a[0]))
        for path in self._dual_write_paths(self._NFT_BLOCK_NUMBER_FILE_NAME):
            with open(path, 'w') as f:
                json.dump(block_number, f)

    def get_cache_nft_block_number(self):
        cache_file_full_path = os.path.join(self._yesterday_cache_full_path, self._NFT_BLOCK_NUMBER_FILE_NAME)
        # if not os.path.exists(cache_file_full_path):
        #     if not self.get_yesterday_cache():
        #         return None
        if not os.path.exists(cache_file_full_path):
            return None
        with open(cache_file_full_path, 'r') as f:
            data = json.load(f)
            return data

    def save_cache_contract_and_user(self, contract_and_user):
        for path in self._dual_write_paths(self._CONTRACT_AND_USER_FILE_NAME):
            with open(path, 'wb') as f:
                pickle.dump(contract_and_user, f, protocol=pickle.DEFAULT_PROTOCOL)

    def get_cache_contract_and_user(self):
        cache_file_full_path = os.path.join(self._yesterday_cache_full_path, self._CONTRACT_AND_USER_FILE_NAME)
        # if not os.path.exists(cache_file_full_path):
        #     if not self.get_yesterday_cache():
        #         return None
        with open(cache_file_full_path, 'rb') as f:
            data = pickle.load(f)
            return data

    def save_cache_pr(self, pr):
        for path in self._dual_write_paths(self._PR_FILE_NAME):
            with open(path, 'w') as f:
                json.dump(pr, f)

    def get_cache_pr(self):
        cache_file_full_path = os.path.join(self._yesterday_cache_full_path, self._PR_FILE_NAME)
        # if not os.path.exists(cache_file_full_path):
        #     if not self.get_yesterday_cache():
        #         return None
        with open(cache_file_full_path, 'r') as f:
            data = json.load(f)
            return data

    def save_cache_input_data(self, input_data):
        for path in self._dual_write_paths(self._INPUT_DATA_FILE_NAME):
            with open(path, 'wb') as f:
                pickle.dump(input_data, f, protocol=pickle.DEFAULT_PROTOCOL)

    def get_cache_input_data(self):
        cache_file_full_path = os.path.join(self._yesterday_cache_full_path, self._INPUT_DATA_FILE_NAME)
        # if not os.path.exists(cache_file_full_path):
        #     if not self.get_yesterday_cache():
        #         return None
        with open(cache_file_full_path, 'rb') as f:
            data = pickle.load(f)
            return data

    # def save_cache_pr_coe(self, pr_coe):
    #     with open(os.path.join(self._cache_full_path, self._PR_COE_FILE_NAME), 'w') as f:
    #         json.dump(pr_coe, f)
    #
    # def get_cache_pr_coe(self):
    #     cache_file_full_path = os.path.join(self._yesterday_cache_full_path, self._PR_COE_FILE_NAME)
    #     # if not os.path.exists(cache_file_full_path):
    #     #     if not self.get_yesterday_cache():
    #     #         return None
    #     with open(cache_file_full_path, 'r') as f:
    #         data = json.load(f)
    #         return data

    def save_earnings_top_nodes(self, earnings_datas):
        earnings_datas = sorted(earnings_datas, key=lambda a: a['address'])
        for path in self._dual_write_paths(self._EARNINGS_TOP_NODES_DATAS_FILE_NAME):
            with open(path, 'w') as f:
                json.dump(earnings_datas, f)

    def save_pledge_datas(self, pledge_datas):
        for path in self._dual_write_paths(self._PLEDGE_DATAS_FILE_NAME):
            with open(path, 'w') as f:
                json.dump(pledge_datas, f)

    def get_cache_pledge_datas(self):
        with open(os.path.join(self._yesterday_cache_full_path, self._PLEDGE_DATAS_FILE_NAME), 'r') as f:
            return json.load(f)

    def save_pledge_block_number(self, end_block_number):
        end_block_number = OrderedDict(sorted(end_block_number.items(), key=lambda a: a[0]))
        for path in self._dual_write_paths(self._PLEDGE_BLOCK_NUMBER_FILE_NAME):
            with open(path, 'w') as f:
                json.dump(end_block_number, f)

    def get_cache_pledge_block_number(self):
        with open(os.path.join(self._yesterday_cache_full_path, self._PLEDGE_BLOCK_NUMBER_FILE_NAME), 'r') as f:
            return json.load(f)

    def save_earnings_pledge(self, earnings_datas):
        earnings_datas = sorted(earnings_datas, key=lambda a: a['address'])
        for path in self._dual_write_paths(self._EARNINGS_PLEDGE_DATAS_FILE_NAME):
            with open(path, 'w') as f:
                json.dump(earnings_datas, f)

    def save_liquidity_datas(self, liquidity_datas):
        for path in self._dual_write_paths(self._LIQUIDITY_DATAS_FILE_NAME):
            with open(path, 'w') as f:
                json.dump(liquidity_datas, f)

    def get_cache_liquidity_datas(self):
        with open(os.path.join(self._yesterday_cache_full_path, self._LIQUIDITY_DATAS_FILE_NAME), 'r') as f:
            return json.load(f)

    def save_private_placement_liquidity_datas(self, datas):
        for path in self._dual_write_paths(self._PRIVATE_PLACEMENT_LIQUIDITY_FILE_NAME):
            with open(path, 'w') as f:
                json.dump(datas, f)

    def get_cache_private_placementliquidity_datas(self):
        with open(os.path.join(self._yesterday_cache_full_path, self._PRIVATE_PLACEMENT_LIQUIDITY_FILE_NAME), 'r') as f:
            return json.load(f)

    def save_liquidity_block_number(self, end_block_number):
        for path in self._dual_write_paths(self._LIQUIDITY_BLOCK_NUMBER_FILE_NAME):
            with open(path, 'w') as f:
                json.dump(end_block_number, f)

    def get_cache_liquidity_block_number(self):
        with open(os.path.join(self._yesterday_cache_full_path, self._LIQUIDITY_BLOCK_NUMBER_FILE_NAME), 'r') as f:
            return json.load(f)

    def save_liquidity_percentages(self, percentage_datas):
        for path in self._dual_write_paths(self._LIQUIDITY_PERCENTAGE_DATAS_FILE_NAME):
            with open(path, 'w') as f:
                json.dump(percentage_datas, f)

    def get_cache_liquidity_percentages(self):
        with open(os.path.join(self._yesterday_cache_full_path, self._LIQUIDITY_PERCENTAGE_DATAS_FILE_NAME), 'r') as f:
            return json.load(f)

    def save_earnings_liquidity(self, earnings_datas):
        earnings_datas = sorted(earnings_datas, key=lambda a: a['address'])
        for path in self._dual_write_paths(self._EARNINGS_LIQUIDITY_DATAS_FILE_NAME):
            with open(path, 'w') as f:
                json.dump(earnings_datas, f)

    def save_earnings_main_pr(self, earnings_datas):
        earnings_datas = sorted(earnings_datas, key=lambda a: a['address'])
        for path in self._dual_write_paths(self._EARNINGS_MAIN_PR_DATAS_FILE_NAME):
            with open(path, 'w') as f:
                json.dump(earnings_datas, f)

    def save_earnings_net_pr(self, earnings_datas):
        earnings_datas = sorted(earnings_datas, key=lambda a: a['address'])
        for path in self._dual_write_paths(self._EARNINGS_NET_PR_DATAS_FILE_NAME):
            with open(path, 'w') as f:
                json.dump(earnings_datas, f)

    def save_earnings_alone_pr(self, earnings_datas):
        file_path = os.path.join(self._cache_full_path, self._EARNINGS_ALONE_PR_DATAS_FILE_NAME)
        if os.path.exists(file_path):
            with open(file_path, 'r') as rf:
                data = json.load(rf)
            earnings_datas.extend(data)
        earnings_datas = sorted(earnings_datas, key=lambda a: a['address'])
        for path in self._dual_write_paths(self._EARNINGS_ALONE_PR_DATAS_FILE_NAME):
            with open(path, 'w') as wf:
                json.dump(earnings_datas, wf)

    def save_top_nodes(self, top_nodes_info):
        # top_nodes = [sorted(top_nodes_info[0]), sorted(top_nodes_info[1])]
        top_nodes = top_nodes_info[:-1]
        for path in self._dual_write_paths(self._TOP_NODES_FILE_NAME):
            with open(path, 'w') as f:
                json.dump(top_nodes, f)

    def get_today_top_nodes(self, index=0):
        with open(os.path.join(self._cache_full_path, self._TOP_NODES_FILE_NAME), 'r') as f:
            return json.load(f)[index]

    def save_prefetching_block_number(self, data):
        for path in self._dual_write_paths(self._PREFETCHING_EVENT_BLOCK_NUMBER_FILE_NAME):
            with open(path, 'w') as f:
                json.dump(data, f)

    def save_senators_info(self, senators_info):
        for path in self._dual_write_paths(self._SENATORS_FILE_NAME):
            with open(path, 'w') as f:
                json.dump(senators_info, f)

    def get_today_senators_info(self):
        with open(os.path.join(self._cache_full_path, self._SENATORS_FILE_NAME), 'r') as f:
            return json.load(f)

    def save_cache_pr_agf(self, pr):
        for path in self._dual_write_paths(self._AGF_PR_FILE_NAME):
            with open(path, 'w') as f:
                json.dump(pr, f)

    def save_cache_pr_agf_normalize(self, pr):
        for path in self._dual_write_paths(self._AGF_PR_FILE_NAME_NM):
            with open(path, 'w') as f:
                json.dump(pr, f)

    def save_cache_pr_cc(self, pr):
        for path in self._dual_write_paths(self._CC_PR_FILE_NAME):
            with open(path, 'w') as f:
                json.dump(pr, f)



    def download_agf_multiplier(self, logger=None):

        domain = app_config.DOMAIN
        date = self._cache_date

        os.makedirs(os.path.dirname(self._cache_full_path), exist_ok=True)
        file_full_path = os.path.join(self._cache_full_path, self._AGF_MULTIPLIER_NAME)
        try:
             for attempt in range(3):
                try:
                    api_url = f"{app_config.AGF_BASE_URL[0]}/{domain}/{date}/{self._AGF_MULTIPLIER_NAME}"

                    if logger:
                        logger.info(f'Calling AGF multiplier API: {api_url}')

                    # Download from signed URL with retry logic
                    for download_attempt in range(3):
                        try:
                            response = requests.get(api_url, timeout=90)
                            response.raise_for_status()

                            with open(file_full_path, 'wb') as wf:
                                wf.write(response.content)

                            decrypt_file_inplace(file_full_path, date, domain)

                            # Downloads/decrypts once to file_full_path (the
                            # main folder) above, then copies the finished
                            # result into the boost folder rather than
                            # re-downloading/re-decrypting a second time.
                            for path in self._dual_write_paths(self._AGF_MULTIPLIER_NAME):
                                if path != file_full_path:
                                    shutil.copy2(file_full_path, path)

                            if logger:
                                logger.info(f'AGF multiplier downloaded successfully to {file_full_path}')

                            return f'AGF multiplier downloaded successfully to {file_full_path}'

                        except requests.exceptions.RequestException as e:
                            if logger:
                                logger.info(f'Download attempt {download_attempt+1} failed: {e}')
                            if download_attempt < 2:
                                time.sleep(3)
                            else:
                                # If all download attempts failed, try getting a new signed URL
                                if attempt < 2:
                                    if logger:
                                        logger.info(f'All download attempts failed, retrying API call (attempt {attempt+2})')
                                    time.sleep(3)
                                    break  # Break inner loop to retry API call
                                else:
                                    raise e

                    # If we reach here, download was successful
                    break

                except (requests.exceptions.RequestException, ValueError) as e:
                    if logger:
                        logger.info(f'API call attempt {attempt+1} failed: {e}')
                    if attempt < 2:
                        time.sleep(3)
                    else:
                        raise e

        except Exception as e:
            error_msg = f"Failed to download AGF Multiplier: {e}"
            if logger:
                logger.info(error_msg)
            return error_msg

        return f'AGF multiplier downloaded successfully to {file_full_path}'


    def get_today_agf_multiplier(self):
        file_full_path = os.path.join(self._cache_full_path, self._AGF_MULTIPLIER_NAME)
        try:
            with open(file_full_path, 'r') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                else:
                    # If the file exists but is not a list, return empty list
                    return []
        except Exception as e:
            # Optionally log the error here
            # print(f"Error reading AGF multiplier: {e}")
            return []

    _BOOST_DATA_SUFFIX = '-boost'

    def _boost_output_dir(self):
        """Where the boost jobs (calculate_boost_job, reward_boost_pr_job)
        write their per-date output: boost_pr.json, boost_reward.json,
        boost_pr_source.json, and (via save_boost_day_amount) the
        boost_reward carve-out inside day_amount.json. BOOST_DATA_DIR
        (settings.cfg, True/False), no code change needed to switch:
          - True (the default): a same-dated sibling folder,
            data_dir/<date>-boost/ - e.g. a '2026-07-28' PR folder gets a
            '2026-07-28-boost' companion, so boost output can be verified
            side by side without touching the live pipeline's own folder or
            its consensus dataset. Naturally survives both existing cleanup
            jobs: data_job's delete_datas() only ever touches the exact
            self.today_path (no suffix) it's handed, and del_old_datas_job's
            "delete if dirname <= cutoff_date" sweep never matches a
            suffixed name, since appending characters to a valid date string
            always sorts it after the bare date.
          - False: falls back to the plain dated folder
            (self._cache_full_path) - the same folder as everything else
            that day. This is what makes boost_pr.json/boost_reward.json
            part of the real per-day dataset (hash-compared against the
            executer alongside pr.json etc., per data_job) - flip this once
            boost output is trusted enough to be a required part of the
            live consensus snapshot.
        """
        isolated = getattr(app_config, 'BOOST_DATA_DIR', True)
        path = self._cache_full_path + self._BOOST_DATA_SUFFIX if isolated else self._cache_full_path
        if not os.path.exists(path):
            os.makedirs(path)
        return path

    def save_cache_pr_boost(self, shares, total_points):
        """Stores each wallet's share of the BOOST_LOOKBACK_DAYS window's total
        points, e.g. {"0xabc...": "0.1"} meaning that wallet holds 10% of all
        points across every user that window - same 0-1 fraction-of-total shape
        as pr.json, just flat (boost has no per-coin split). total_points (the
        window's raw point total the shares were computed against) is kept
        alongside so it's readable without re-deriving it from boost memory."""
        data = {'total_points': str(total_points), 'shares': shares}
        with open(os.path.join(self._boost_output_dir(), self._BOOST_PR_FILE_NAME), 'w') as f:
            json.dump(data, f)

    def save_boost_pr_source(self, pr, source_date):
        """Copies the pr.json calculate_boost_job actually read eligibility
        from into today's boost folder, tagged with the date it came from -
        _previous_pr() can fall back to an older day if the main PR job was
        delayed, so this makes it possible to tell which day's pr.json a
        given boost_pr.json was computed against without cross-referencing
        logs or relying on the source file still existing/unchanged later."""
        with open(os.path.join(self._boost_output_dir(), self._BOOST_PR_SOURCE_FILE_NAME), 'w') as f:
            json.dump({'source_date': source_date, 'pr': pr}, f)

    def get_today_pr_boost(self):
        """Returns {'total_points': str, 'shares': {address: share (str, 0-1
        fraction of the window's total points)}}."""
        with open(os.path.join(self._boost_output_dir(), self._BOOST_PR_FILE_NAME), 'r') as f:
            return json.load(f)

    def save_reward_boost(self, reward_datas):
        reward_datas = sorted(reward_datas, key=lambda a: a['address'])
        with open(os.path.join(self._boost_output_dir(), self._BOOST_REWARD_FILE_NAME), 'w') as f:
            json.dump(reward_datas, f)

    def get_boost_memory(self):
        """Cursor (last dateKey already scanned per instance address) + history
        (previously fetched rows for those dateKeys), read from a single
        persistent path OUTSIDE any dated data_dir/<date>/ folder - unlike
        the rest of this class's per-day caches, this one has to survive
        data_job's delete_datas() wiping today's folder mid-cycle and outlive
        a single boost day, since a failed vote should resume from the last
        good fetch rather than an empty one. Returns {} on the very first
        run before it's ever been written, which GameHubReader.fetch_all
        treats as "fetch the full lookback window". May also carry a
        'ready_date' key (see save_boost_memory/wait_memory)."""
        file_full_path = os.path.join(self._cache_path, self._BOOST_MEMORY_FILE_NAME)
        if not os.path.exists(file_full_path):
            return {}
        with open(file_full_path, 'r') as f:
            return json.load(f)

    def save_boost_memory(self, memory):
        with open(os.path.join(self._cache_path, self._BOOST_MEMORY_FILE_NAME), 'w') as f:
            json.dump(memory, f)
