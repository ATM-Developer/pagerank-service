import requests
import json


class AtmUtil:

    def __init__(self, url):
        self._url = url

    def get_coin_list(self):
        res = requests.get(self._url + '/site/getCoinCurrencyList')
        result = json.loads(res.text)
        data_list = result.get('data', {}).get('coinCurrencyPairList', [])
        coin_list = {}
        for data in data_list:
            symbol = data['baseCurrency'].upper()
            coin_list[symbol] = {
                'coefficient': data['coefficient'],
                'decimals': int(data['weiPlaces'])
            }
        return coin_list
