import os
import json
import pickle
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

    _AGF_PR_FILE_NAME = 'agf_pr.json'
    _AGF_MULTIPLIER_NAME = 'agf_multiplier.json'
    _AGF_PR_FILE_NAME_NM = 'agf_pr_normalize.json'

    def __init__(self, date_type='pagerank'):
        """

        :param date_type: pagerank, the date of PageRank Calculating
                          time, UTC date
        """
        self._cache_path = get_cfg('setting', 'data_dir', path_join=True)
        self._cache_date = get_pagerank_date() if date_type == 'pagerank' else time_format()[:10]
        if date_type == 'pagerank':
            self._yesterday_cache_date = get_previous_pagerank_date()
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
        with open(os.path.join(self._cache_full_path, self._COIN_LIST_FILE_NAME), 'w') as f:
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

    def get_today_day_amount(self):
        getcontext().prec = 100
        file_full_path = os.path.join(self._cache_full_path, self._DAY_AMOUNT_FILE_NAME)
        with open(file_full_path, 'r') as f:
            data = json.load(f)
            for k, v in data.items():
                data[k] = Decimal(str(v))
            return data

    def save_cache_coin_price(self, coin_price):
        coin_price = OrderedDict(sorted(coin_price.items(), key=lambda a: a[0]))
        with open(os.path.join(self._cache_full_path, self._COIN_PRICE_FILE_NAME), 'w') as f:
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
        with open(os.path.join(self._cache_full_path, self._COIN_PRICE_TEMP_FILE_NAME), 'w') as f:
            json.dump(coin_price, f)

    def get_today_coin_price_temp(self):
        file_full_path = os.path.join(self._cache_full_path, self._COIN_PRICE_TEMP_FILE_NAME)
        with open(file_full_path, 'r') as f:
            data = json.load(f)
            return data

    def save_cache_block_number(self, block_number):
        block_number = OrderedDict(sorted(block_number.items(), key=lambda a: a[0]))
        with open(os.path.join(self._cache_full_path, self._BLOCK_NUMBER_FILE_NAME), 'w') as f:
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
        with open(os.path.join(self._cache_full_path, self._NFT_BLOCK_NUMBER_FILE_NAME), 'w') as f:
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
        with open(os.path.join(self._cache_full_path, self._CONTRACT_AND_USER_FILE_NAME), 'wb') as f:
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
        with open(os.path.join(self._cache_full_path, self._PR_FILE_NAME), 'w') as f:
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
        with open(os.path.join(self._cache_full_path, self._INPUT_DATA_FILE_NAME), 'wb') as f:
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
        with open(os.path.join(self._cache_full_path, self._EARNINGS_TOP_NODES_DATAS_FILE_NAME), 'w') as f:
            json.dump(earnings_datas, f)

    def save_pledge_datas(self, pledge_datas):
        with open(os.path.join(self._cache_full_path, self._PLEDGE_DATAS_FILE_NAME), 'w') as f:
            json.dump(pledge_datas, f)

    def get_cache_pledge_datas(self):
        with open(os.path.join(self._yesterday_cache_full_path, self._PLEDGE_DATAS_FILE_NAME), 'r') as f:
            return json.load(f)

    def save_pledge_block_number(self, end_block_number):
        end_block_number = OrderedDict(sorted(end_block_number.items(), key=lambda a: a[0]))
        with open(os.path.join(self._cache_full_path, self._PLEDGE_BLOCK_NUMBER_FILE_NAME), 'w') as f:
            json.dump(end_block_number, f)

    def get_cache_pledge_block_number(self):
        with open(os.path.join(self._yesterday_cache_full_path, self._PLEDGE_BLOCK_NUMBER_FILE_NAME), 'r') as f:
            return json.load(f)

    def save_earnings_pledge(self, earnings_datas):
        earnings_datas = sorted(earnings_datas, key=lambda a: a['address'])
        with open(os.path.join(self._cache_full_path, self._EARNINGS_PLEDGE_DATAS_FILE_NAME), 'w') as f:
            json.dump(earnings_datas, f)

    def save_liquidity_datas(self, liquidity_datas):
        with open(os.path.join(self._cache_full_path, self._LIQUIDITY_DATAS_FILE_NAME), 'w') as f:
            json.dump(liquidity_datas, f)

    def get_cache_liquidity_datas(self):
        with open(os.path.join(self._yesterday_cache_full_path, self._LIQUIDITY_DATAS_FILE_NAME), 'r') as f:
            return json.load(f)

    def save_private_placement_liquidity_datas(self, datas):
        with open(os.path.join(self._cache_full_path, self._PRIVATE_PLACEMENT_LIQUIDITY_FILE_NAME), 'w') as f:
            json.dump(datas, f)

    def get_cache_private_placementliquidity_datas(self):
        with open(os.path.join(self._yesterday_cache_full_path, self._PRIVATE_PLACEMENT_LIQUIDITY_FILE_NAME), 'r') as f:
            return json.load(f)

    def save_liquidity_block_number(self, end_block_number):
        with open(os.path.join(self._cache_full_path, self._LIQUIDITY_BLOCK_NUMBER_FILE_NAME), 'w') as f:
            json.dump(end_block_number, f)

    def get_cache_liquidity_block_number(self):
        with open(os.path.join(self._yesterday_cache_full_path, self._LIQUIDITY_BLOCK_NUMBER_FILE_NAME), 'r') as f:
            return json.load(f)

    def save_liquidity_percentages(self, percentage_datas):
        with open(os.path.join(self._cache_full_path, self._LIQUIDITY_PERCENTAGE_DATAS_FILE_NAME), 'w') as f:
            json.dump(percentage_datas, f)

    def get_cache_liquidity_percentages(self):
        with open(os.path.join(self._yesterday_cache_full_path, self._LIQUIDITY_PERCENTAGE_DATAS_FILE_NAME), 'r') as f:
            return json.load(f)

    def save_earnings_liquidity(self, earnings_datas):
        earnings_datas = sorted(earnings_datas, key=lambda a: a['address'])
        with open(os.path.join(self._cache_full_path, self._EARNINGS_LIQUIDITY_DATAS_FILE_NAME), 'w') as f:
            json.dump(earnings_datas, f)

    def save_earnings_main_pr(self, earnings_datas):
        earnings_datas = sorted(earnings_datas, key=lambda a: a['address'])
        with open(os.path.join(self._cache_full_path, self._EARNINGS_MAIN_PR_DATAS_FILE_NAME), 'w') as f:
            json.dump(earnings_datas, f)

    def save_earnings_net_pr(self, earnings_datas):
        earnings_datas = sorted(earnings_datas, key=lambda a: a['address'])
        with open(os.path.join(self._cache_full_path, self._EARNINGS_NET_PR_DATAS_FILE_NAME), 'w') as f:
            json.dump(earnings_datas, f)

    def save_earnings_alone_pr(self, earnings_datas):
        file_path = os.path.join(self._cache_full_path, self._EARNINGS_ALONE_PR_DATAS_FILE_NAME)
        if os.path.exists(file_path):
            with open(file_path, 'r') as rf:
                data = json.load(rf)
            earnings_datas.extend(data)
        earnings_datas = sorted(earnings_datas, key=lambda a: a['address'])
        with open(file_path, 'w') as wf:
            json.dump(earnings_datas, wf)

    def save_top_nodes(self, top_nodes_info):
        # top_nodes = [sorted(top_nodes_info[0]), sorted(top_nodes_info[1])]
        top_nodes = top_nodes_info[:-1]
        with open(os.path.join(self._cache_full_path, self._TOP_NODES_FILE_NAME), 'w') as f:
            json.dump(top_nodes, f)

    def get_today_top_nodes(self, index=0):
        with open(os.path.join(self._cache_full_path, self._TOP_NODES_FILE_NAME), 'r') as f:
            return json.load(f)[index]

    def save_prefetching_block_number(self, data):
        with open(os.path.join(self._cache_full_path, self._PREFETCHING_EVENT_BLOCK_NUMBER_FILE_NAME), 'w') as f:
            json.dump(data, f)

    def save_senators_info(self, senators_info):
        with open(os.path.join(self._cache_full_path, self._SENATORS_FILE_NAME), 'w') as f:
            json.dump(senators_info, f)

    def get_today_senators_info(self):
        with open(os.path.join(self._cache_full_path, self._SENATORS_FILE_NAME), 'r') as f:
            return json.load(f)

    def save_cache_pr_agf(self, pr):
        with open(os.path.join(self._cache_full_path, self._AGF_PR_FILE_NAME), 'w') as f:
            json.dump(pr, f)

    def save_cache_pr_agf_normalize(self, pr):
        with open(os.path.join(self._cache_full_path, self._AGF_PR_FILE_NAME_NM), 'w') as f:
            json.dump(pr, f)
   


    
    def download_agf_multiplier(self, logger=None):

        domain = app_config.DOMAIN
        date = self._cache_date
        
        os.makedirs(os.path.dirname(self._cache_full_path), exist_ok=True)
        file_full_path = os.path.join(self._cache_full_path, self._AGF_MULTIPLIER_NAME)

        try:
             for attempt in range(3):
                try:
                    api_url = f"{app_config.AGF_BASE_URL[0]}/web2/api/v1/agf-multiplier-url"
                    payload = {
                        "domain": domain,
                        "date": date
                    }
                    
                    if logger:
                        logger.info(f'Calling AGF multiplier API: {api_url} with payload: {payload}')
                    
                    api_response = requests.post(api_url, json=payload)
                    api_response.raise_for_status()
                    
                    response_data = api_response.json()
                    signed_url = response_data.get('signed_url')
                    
                    if not signed_url:
                       raise ValueError("No signed_url in API response")
                    
                    if logger:
                        logger.info(f'AGF multiplier signed URL obtained: {signed_url}')
                    
                    # Download from signed URL with retry logic
                    for download_attempt in range(3):
                        try:
                            response = requests.get(signed_url)
                            response.raise_for_status()
                            
                            with open(file_full_path, 'wb') as wf:
                                wf.write(response.content)

                            decrypt_file_inplace(file_full_path, date, domain)
                            
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