import requests
import json
import time
import traceback


class AtmUtil:

    def __init__(self, url):
        self._url = url
        self._retry = 3

    def get_coin_list(self):
        coin_data1 = self.__request_con_list(self._url + '/site/getCoinCurrencyList?chainId=1')
        if coin_data1 is None:
            return None
        coin_data2 = self.__request_con_list(self._url + '/site/getCoinCurrencyList?chainId=2')
        if coin_data2 is None:
            return None
        coin_data = coin_data2
        coin_data.update(coin_data1)
        return coin_data

    def __request_con_list(self, url):
        for i in range(self._retry):
            try:
                res = requests.get(url)
                result = json.loads(res.text)
                if result.get('success') is True:
                    data_list = result.get('data', {}).get('coinCurrencyPairList', [])
                    coin_list = {}
                    for data in data_list:
                        symbol = data['baseCurrency'].upper()
                        coin_list[symbol] = {
                            'coefficient': data['coefficient'],
                            'decimals': int(data['weiPlaces']),
                            'alone_calculate': int(data['aloneCalculateFlag']),
                            'contract_address': data['contractAddress'],
                            'gateway': data['gateWay'],
                            'chain_id': data['chainId'],
                            'now_price': data['nowPrice']
                        }
                    return coin_list
                else:
                    time.sleep(3)
                    continue
            except Exception as e:
                print(e)
                print(traceback.format_exc())
                time.sleep(3)
                continue
        return None

    def get_link_rate(self):
        for i in range(self._retry):
            try:
                res = requests.get(self._url + '/site/getLucaAmount')
                result = json.loads(res.text)
                rate = result.get('data', {}).get('linkUsdRate', -1)
                if rate != -1:
                    return float(rate)
                else:
                    time.sleep(3)
                    continue
            except Exception as e:
                print(e)
                print(traceback.format_exc())
                time.sleep(3)
                continue
        return None
