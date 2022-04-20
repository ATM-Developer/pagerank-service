import requests
import json
import time
import traceback


class AtmUtil:

    def __init__(self, url):
        self._url = url
        self._retry = 3

    def get_coin_list(self):
        for i in range(self._retry):
            try:
                res = requests.get(self._url + '/site/getCoinCurrencyList')
                result = json.loads(res.text)
                data_list = result.get('data', {}).get('coinCurrencyPairList', [])
                coin_list = {}
                for data in data_list:
                    symbol = data['baseCurrency'].upper()
                    coin_list[symbol] = {
                        'coefficient': data['coefficient'],
                        'decimals': int(data['weiPlaces']),
                        'alone_calculate': int(data['aloneCalculateFlag']),
                        'contract_address': data['contractAddress'],
                        'gateway': data['gateWay']
                    }
                if coin_list != {}:
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
