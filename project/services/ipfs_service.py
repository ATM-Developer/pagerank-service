
import json
import time
import os
import random
import requests
import traceback
import subprocess
from threading import Thread
from project.extensions import app_config


def download_chunk(url, start, end, result, index, headers):
    headers.update({'Range': f'bytes={start}-{end}'})
    response = requests.get(url, headers=headers)
    result[index] = response.content


def download_file(url, number_of_chunks, headers):
    file_size = 0
    try:
        response = requests.head(url, headers=headers)
        file_size = int(response.headers.get('content-length', 0))
        chunk_size = file_size // number_of_chunks
        threads = []
        results = [None] * number_of_chunks

        for i in range(number_of_chunks):
            start = i * chunk_size
            # Ensure that the last block retrieves all remaining data
            end = start + chunk_size - 1 if i < number_of_chunks - 1 else file_size
            thread = Thread(target=download_chunk, args=(url, start, end, results, i, headers))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join(60)

        return file_size, b''.join(results)
    except:
        return file_size, b''


class IPFS:

    def __init__(self, logger):
        self.logger = logger
        self._retry = 3
        self._delay = 3
    
    def __upload_with_url(self, file_path):
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
    
    def __upload_with_command(self, file_path):
        conmmand = ["w3", "up", file_path, "--json"]
        self.logger.info(conmmand)
        result = subprocess.run(
            conmmand,
            stdout=subprocess.PIPE,
            text=True,
        )
        self.logger.info(result.stdout)
        result = json.loads(result.stdout)
        cid = result.get("root", {}).get("/")
        return cid

    def upload(self, file_path):
        if not file_path:
            return None
        for i in range(self._retry):
            try:
                # return self.__upload_with_url(file_path)
                return self.__upload_with_command(file_path)
            except Exception as e:
                self.logger.error(traceback.format_exc())
                time.sleep(self._delay)
        return None

    def _get_url(self, cid, file_name):
        # backup
        if file_name < app_config.NEW_IPFS_DATE:
            return ['https://{}.ipfs.dweb.link'.format(cid)]
            # return '{}{}'.format(self.ipfs_prefix, cid)
        else:
            this_name = file_name.replace('_executer', '')
            GATEWAYS=(
                # "https://ipfs.io/ipfs",
                # "https://cloudflare-ipfs.com/ipfs",
                # "https://dweb.link/ipfs",
                "https://gateway.pinata.cloud/ipfs",
                # "https://nftstorage.link/ipfs",
                # "https://cf-ipfs.com/ipfs",
                # "https://4everland.io/ipfs",
            )
            urls = [
                f"{host}/{cid}/{this_name}"
                for host in GATEWAYS
            ]
            urls.extend([
                "https://{}.ipfs.w3s.link/{}".format(cid, this_name),
                "https://{}.ipfs.dweb.link/{}".format(cid, this_name),
                "https://{}.ipfs.storacha.link/{}".format(cid, this_name),
            ])
            return urls

    def download(self, cid, folder, file_name):
        if not cid:
            return False
        if not folder:
            return False
        else:
            if not os.path.exists(folder):
                os.makedirs(folder)
        urls = self._get_url(cid, file_name)
        headers = {
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
        }
        check_file_size = 500000
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
                for url in urls:
                    self.logger.info(f'Segmented download: {url}')
                    flag, results = download_file(url, 10, headers)
                    self.logger.info(f'request download file size: {flag}')
                    if len(results) > check_file_size:
                        with open(os.path.join(folder, file_name), 'wb') as wf:
                            wf.write(results)
                        self.logger.info(f'Segmented download ok. file size: {flag}')
                        return True
                    file_size = 0
                    for command in [
                        'curl -m 60 -H "User-Agent: {}" {} -o {}'.format(headers["user-agent"], url, os.path.join(folder, file_name)),
                        'wget --header="User-Agent: {}" --timeout=60 {} -O {}'.format(headers["user-agent"], url, os.path.join(folder, file_name))
                    ]:
                        try:
                            self.logger.info('use command: {}'.format(command))
                            os.system(command)
                            self.logger.info('os download ok')
                            file_size = os.stat(os.path.join(folder, file_name)).st_size
                            self.logger.info('file size: {}'.format(file_size))
                            if file_size > check_file_size:
                                self.logger.info(f'file size {file_size} ok')
                                return True
                        except:
                            pass
                    time.sleep(random.randint(0, 10))
            except Exception as e:
                self.logger.error(traceback.format_exc())
                time.sleep(self._delay)
        return False
