import requests
import json


class HttpHelper:
    def __init__(self, base_url) -> None:
        self.base_url = base_url

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
