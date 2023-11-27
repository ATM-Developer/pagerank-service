import requests
import json
import time
import os
import random
import traceback
from threading import Thread
from project.extensions import app_config


def download_chunk(url, start, end, result, index):
    headers = {'Range': f'bytes={start}-{end}'}
    response = requests.get(url, headers=headers)
    result[index] = response.content


def download_file(url, number_of_chunks):
    try:
        response = requests.head(url)
        file_size = int(response.headers.get('content-length', 0))
        chunk_size = file_size // number_of_chunks
        threads = []
        results = [None] * number_of_chunks

        for i in range(number_of_chunks):
            start = i * chunk_size
            # Ensure that the last block retrieves all remaining data
            end = start + chunk_size - 1 if i < number_of_chunks - 1 else file_size
            thread = Thread(target=download_chunk, args=(url, start, end, results, i))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join(60)

        return True, b''.join(results)
    except:
        return False, b''


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
                self.logger.info('Segmented download')
                flag, results = download_file(url, 10)
                if flag:
                    with open(os.path.join(folder, file_name), 'wb') as wf:
                        wf.write(results)
                    self.logger.info('Segmented download ok.')
                    return True
                file_size = 0
                for command in [
                    'curl -m 60 {} -o {}'.format(url, os.path.join(folder, file_name)),
                    'wget --timeout=60 {} -O {}'.format(url, os.path.join(folder, file_name))
                ]:
                    try:
                        self.logger.info('use command: {}'.format(command))
                        os.system(command)
                        self.logger.info('os download ok')
                        file_size = os.stat(os.path.join(folder, file_name)).st_size
                        self.logger.info('file size: {}'.format(file_size))
                        if file_size > 10000:
                            break
                    except:
                        pass
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
