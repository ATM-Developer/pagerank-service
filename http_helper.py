import requests
import json
import time


class HttpHelper:
    def __init__(self, base_url) -> None:
        self.base_url = base_url
        self._retry = 3

    def get_lastday_cache(self, cache_folder):
        local_filename = cache_folder + '/last_day_edge_multi_contract.pickle'
        get_cache1_url_response = requests.get(self.base_url + '/api/getLastDayCache1')
        res1 = json.loads(get_cache1_url_response.text)
        if 'url' in res1:
            cache1_response = requests.get(res1['url'])
            if (cache1_response.status_code == 200):
                with open(local_filename, 'wb') as f:
                    for chunk in cache1_response.iter_content(chunk_size=512 * 1024):
                        if chunk:  # filter out keep-alive new chunks
                            f.write(chunk)

        local_filename = cache_folder + '/recent_transaction_hash.txt'
        get_cache2_url_response = requests.get(self.base_url + '/api/getLastDayCache2')
        res2 = json.loads(get_cache2_url_response.text)
        if 'url' in res2:
            cache2_response = requests.get(res2['url'])
            if (cache2_response.status_code == 200):
                with open(local_filename, 'wb') as f:
                    for chunk in cache2_response.iter_content(chunk_size=512 * 1024):
                        if chunk:  # filter out keep-alive new chunks
                            f.write(chunk)

    def notify_completion(self, wallet_address):
        requests.get(self.base_url + '/api/notifyCompletion/' + wallet_address.lower())

    def _get_backup_luca_amount(self):
        return requests.get(self.base_url + '/api/atm/getLucaAmount')

    def _get_backup_coin_currency(self):
        return requests.get(self.base_url + '/api/atm/getCoinCurrencyList')

    def get_coin_list(self):
        for i in range(self._retry):
            res = self._get_backup_coin_currency()
            result = json.loads(res.text)
            data_list = result.get('data', {}).get('coinCurrencyPairList', [])
            coin_list = {}
            for data in data_list:
                symbol = data['baseCurrency'].upper()
                if data['chainId'] == 2 and symbol in coin_list:
                    continue
                coin_list[symbol] = {
                    'coefficient': data['coefficient'],
                    'decimals': int(data['weiPlaces']),
                    'alone_calculate': int(data['aloneCalculateFlag']),
                    'contract_address': data['contractAddress'],
                    'gateway': data['gateWay'],
                    'chain_id': data['chainId'],
                    'now_price': data['nowPrice']
                }
            if coin_list != {}:
                return coin_list
            else:
                time.sleep(3)
                continue
        return None

    def get_link_rate(self):
        for i in range(self._retry):
            res = self._get_backup_luca_amount()
            result = json.loads(res.text)
            rate = result.get('data', {}).get('linkUsdRate', -1)
            if rate != -1:
                return float(rate)
            else:
                time.sleep(3)
                continue
        return None
