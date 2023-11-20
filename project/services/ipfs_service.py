import requests
import json
import time
import os
import random
import traceback
from project.extensions import app_config


class IPFS:

    def __init__(self, logger):
        self.logger = logger
        self.url = app_config.IPFS_SERVICE_URL
        self.token = app_config.IPFS_SERVICE_TOKEN
        self.ipfs_prefix = 'https://ipfs.io/ipfs/'
        self._retry = 3
        self._delay = 3

    def upload(self, file_path):
        if not file_path:
            return None
        for i in range(self._retry):
            try:
                payload = {}
                files = [
                    ('file', ('file', open(file_path, 'rb'), 'application/zip'))
                ]
                headers = {
                    'Authorization': 'Bearer {}'.format(self.token)
                }
                response = requests.request('POST', self.url, headers=headers, data=payload, files=files, timeout=900)
                self.logger.info('response: {}'.format(response.text))
                response_json = json.loads(response.text)
                return response_json['cid']
            except Exception as e:
                self.logger.error(traceback.format_exc())
                time.sleep(self._delay)
        return None

    def _get_url(self, cid):
        # backup
        return 'https://{}.ipfs.dweb.link'.format(cid)
        # return '{}{}'.format(self.ipfs_prefix, cid)

    def download(self, cid, folder, file_name):
        if not cid:
            return False
        if not folder:
            return False
        else:
            if not os.path.exists(folder):
                os.makedirs(folder)
        url = self._get_url(cid)
        for i in range(self._retry):
            try:
                # download_response = requests.get(url, stream=True)
                # if download_response.status_code == 200:
                #     with open(os.path.join(folder, file_name), 'wb') as f:
                #         for chunk in download_response.iter_content(chunk_size=512 * 1024):
                #             if chunk:
                #                 f.write(chunk)
                #         return True
                # else:
                #     continue
                os.system('curl {} -o {}'.format(url, os.path.join(folder, file_name)))
                self.logger.info('os download ok')
                file_size = os.stat(os.path.join(folder, file_name)).st_size
                self.logger.info('file size: {}'.format(file_size))
                if file_size > 10000:
                    self.logger.info('file size ok')
                    return True
                else:
                    self.logger.info('file size continue')
                    time.sleep(random.randint(0, 10))
                    continue
            except Exception as e:
                self.logger.error(traceback.format_exc())
                time.sleep(self._delay)
        return False
