
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
    this_headers = dict(headers)
    this_headers.update({'Range': f'bytes={start}-{end}'})
    response = requests.get(url, headers=this_headers, timeout=600)
    result[index] = response.content


def download_file(url, number_of_chunks, headers):
    file_size = 0
    try:
        response = requests.head(url, headers=headers, timeout=60)
        file_size = int(response.headers.get('content-length', 0))
        chunk_size = file_size // number_of_chunks if number_of_chunks else 0
        threads = []
        results = [None] * number_of_chunks

        for i in range(number_of_chunks):
            start = i * chunk_size
            end = start + chunk_size - 1 if i < number_of_chunks - 1 else file_size - 1
            thread = Thread(target=download_chunk, args=(url, start, end, results, i, headers))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join(60)

        if any(item is None for item in results):
            return file_size, b''

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
        conmmand = ["storacha", "up", file_path, "--json"]
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

    
   
    def __upload_with_pinata_command(self, file_path):
        url = app_config.PINATA_URL

        PINATA_JWT = app_config.PINATA_JWT
        headers = {
                "Authorization": "Bearer {}".format(PINATA_JWT)
        }

        with open(file_path, "rb") as f:
            files = {
                "file": (os.path.basename(file_path), f)
            }
            data = {
                "network": "private",
                "pinataOptions": json.dumps({
                    "wrapWithDirectory": True
                }),
                "pinataMetadata": json.dumps({
                    "name": os.path.basename(file_path)
                })
            }

            response = requests.post(
                url,
                headers=headers,
                files=files,
                data=data,
                timeout=900
            )

        self.logger.info("pinata response: {}".format(response.text))
        response.raise_for_status()

        result = response.json()
        cid = result.get("IpfsHash")
        return cid

    def upload(self, file_path):
        if not file_path:
            return None
        for i in range(self._retry):
            try:
                storacha_cid = None
                pinata_cid = None

                # try:
                #     storacha_cid = self.__upload_with_command(file_path)
                # except Exception:
                #     self.logger.error('storacha upload failed')
                #     self.logger.error(traceback.format_exc())

                try:
                    pinata_cid = self.__upload_with_pinata_command(file_path)
                except Exception:
                    self.logger.error('pinata upload failed')
                    self.logger.error(traceback.format_exc())

                # if storacha_cid:
                #     self.logger.info('upload success, storacha_cid: {}, pinata_cid: {}'.format(storacha_cid, pinata_cid))
                #     return storacha_cid

                if pinata_cid:
                    self.logger.info('upload success, pinata_cid: {}'.format(pinata_cid))
                    return pinata_cid

            except Exception:
                self.logger.error(traceback.format_exc())
                time.sleep(self._delay)
        return None

    def _get_pinata_urls(self, cid, file_name):
        if not cid:
            return []

        this_name = file_name.replace('_executer', '')
        return [
            "https://gateway.pinata.cloud/ipfs/{}/{}".format(cid, this_name),
        ]

    def _get_storacha_urls(self, cid, file_name):
        if not cid:
            return []

        if file_name < '2024-01-02':
            return ['https://{}.ipfs.dweb.link/{}'.format(cid, file_name.replace('_executer', ''))]
            # return '{}{}'.format(self.ipfs_prefix, cid)
        else:
            this_name = file_name.replace('_executer', '')
            GATEWAYS = (
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

    def _get_url(self, cid, file_name):
        if isinstance(cid, dict):
            pinata_urls = self._get_pinata_urls(cid.get("pinata_cid"), file_name)
            storacha_urls = self._get_storacha_urls(cid.get("storacha_cid"), file_name)
            return pinata_urls + storacha_urls

        return self._get_pinata_urls(cid, file_name) + self._get_storacha_urls(cid, file_name)

    def download(self, url, target_file_path):
        if not url or not target_file_path:
            return False
        else:
            dir_path = os.path.dirname(target_file_path)
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)
        headers = {
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
        }
        check_file_size = 500000
        urls = url if isinstance(url, list) else [url]
        for one_url in urls:
            for i in range(self._retry):
                try:
                    self.logger.info(f'Segmented download: {one_url}')
                    flag, results = download_file(one_url, 10, headers)
                    self.logger.info(f'request download file size: {flag}')
                    if len(results) > check_file_size:
                        with open(target_file_path, 'wb') as wf:
                            wf.write(results)
                        self.logger.info(f'Segmented download ok. file size: {flag}')
                        return True
                    file_size = 0
                    for command in [
                        'curl -L -m 60 -H "User-Agent: {}" "{}" -o "{}"'.format(headers["user-agent"], one_url, target_file_path),
                        'wget --header="User-Agent: {}" --timeout=60 "{}" -O "{}"'.format(headers["user-agent"], one_url, target_file_path)
                    ]:
                        try:
                            self.logger.info('use command: {}'.format(command))
                            os.system(command)
                            self.logger.info('os download ok')
                            file_size = os.stat(target_file_path).st_size
                            self.logger.info('file size: {}'.format(file_size))
                            if file_size > check_file_size:
                                self.logger.info(f'file size {file_size} ok')
                                return True
                        except:
                            pass
                    time.sleep(random.randint(0, 10))
                except Exception:
                    self.logger.error(traceback.format_exc())
                    time.sleep(self._delay)

        return False

