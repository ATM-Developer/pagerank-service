
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
        # _get_url() now returns only the single real Pinata URL instead of
        # 8 (7 of which were guaranteed-dead public gateways) - that budget
        # is better spent on more, more-widely-spaced retries of the one URL
        # that can actually work, since ~20 fleet nodes reacting to the same
        # on-chain proposal at once tends to hit it in the same few-second
        # window and contend/rate-limit each other.
        self._retry = 5
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
                "https://ipfs.io/ipfs",
                # "https://cloudflare-ipfs.com/ipfs",  # dead: connection fails everywhere
                "https://dweb.link/ipfs",
                "https://gateway.pinata.cloud/ipfs",
                "https://nftstorage.link/ipfs",
                # "https://cf-ipfs.com/ipfs",  # dead: connection fails everywhere
                # "https://4everland.io/ipfs",  # dead: 521 origin down
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

        # upload() only ever returns a bare pinata_cid right now (the
        # storacha upload path above is disabled) - and that CID was pinned
        # with network="private", so it was never announced to the public
        # IPFS DHT. Generic public gateways (ipfs.io, dweb.link, w3s.link,
        # etc.) can never resolve a private-network CID no matter how many
        # times it's retried; only Pinata's own gateway has direct access to
        # it. Appending _get_storacha_urls() here just wastes most of every
        # retry cycle on guaranteed-dead URLs - only try what can work.
        return self._get_pinata_urls(cid, file_name)

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
        # A fixed byte threshold here has already gone stale twice (500000 ->
        # 50000, both meant to sit between "real archive" and "tiny IPFS-
        # gateway error stub" sizes) because real archive size drifts with
        # how much on-chain activity there was that day - e.g. it's ~16KB on
        # this low-activity dev-net right now, well under even the lowered
        # 50000 floor, so every genuinely correct download was being
        # rejected as if it were an error page. download_file() already does
        # a HEAD request and knows the server-reported Content-Length for
        # this exact URL - compare the downloaded bytes against THAT instead
        # of a guessed constant, so this self-corrects as real size changes.
        # min_sane_size is only a last-resort floor for when a gateway's HEAD
        # response has no Content-Length at all (expected_size stays 0).
        min_sane_size = 1000
        urls = url if isinstance(url, list) else [url]
        self.logger.info(f'download: {len(urls)} candidate url(s) to try, {self._retry} attempt(s) each: {urls}')
        for url_index, one_url in enumerate(urls):
            for i in range(self._retry):
                try:
                    self.logger.info(f'Segmented download: url {url_index + 1}/{len(urls)}, '
                                      f'attempt {i + 1}/{self._retry}: {one_url}')
                    expected_size, results = download_file(one_url, 10, headers)
                    self.logger.info(f'request download file size: {expected_size}')
                    size_ok = (len(results) == expected_size if expected_size
                               else len(results) > min_sane_size)
                    if size_ok and results[:2] == b'\x1f\x8b':
                        with open(target_file_path, 'wb') as wf:
                            wf.write(results)
                        self.logger.info(f'Segmented download ok. file size: {expected_size}')
                        return True
                    elif size_ok:
                        self.logger.info(f'file size {len(results)} ok but not valid gzip '
                                          f'(magic={results[:2]!r}), likely an error page, rejecting')
                    elif expected_size:
                        self.logger.info(f'file size {len(results)} does not match expected content-length '
                                          f'{expected_size}, rejecting')
                    file_size = 0
                    for command in [
                        'curl -L -m 60 -H "User-Agent: {}" "{}" -o "{}"'.format(headers["user-agent"], one_url, target_file_path),
                        'wget --header="User-Agent: {}" --timeout=60 "{}" -O "{}"'.format(headers["user-agent"], one_url, target_file_path)
                    ]:
                        try:
                            self.logger.info('use command: {}'.format(command))
                            os.system(command)
                            # "command finished running" only - not a success
                            # signal by itself (curl/wget can exit fine while
                            # having written an empty or error-page body);
                            # the size/magic checks right below are what
                            # actually decide success.
                            self.logger.info('command finished, checking result')
                            file_size = os.stat(target_file_path).st_size
                            self.logger.info('file size: {}'.format(file_size))
                            size_ok = (file_size == expected_size if expected_size
                                       else file_size > min_sane_size)
                            if size_ok:
                                with open(target_file_path, 'rb') as rf:
                                    magic = rf.read(2)
                                if magic == b'\x1f\x8b':
                                    self.logger.info(f'file size {file_size} ok')
                                    return True
                                else:
                                    self.logger.info(f'file size {file_size} ok but not valid gzip '
                                                      f'(magic={magic!r}), likely an error page, rejecting')
                            elif expected_size:
                                self.logger.info(f'file size {file_size} does not match expected content-length '
                                                  f'{expected_size}, rejecting')
                        except:
                            pass
                    # Exponential backoff, not a flat random range: a flat
                    # range doesn't get more conservative as failures repeat,
                    # so if the gateway is specifically throttling this
                    # fleet's IPs after sustained hits (as opposed to a
                    # one-off contention blip), a flat retry rate just keeps
                    # re-triggering the same throttle instead of backing off
                    # from it. Each consecutive failed attempt on this URL
                    # waits roughly twice as long as the last (capped), with
                    # jitter so ~20 nodes' backoff curves don't stay aligned
                    # with each other either.
                    backoff = min(90, 5 * (2 ** i)) + random.uniform(0, 10)
                    self.logger.info(f'attempt {i + 1}/{self._retry} did not yield a valid file, '
                                      f'backing off {backoff:.1f}s before retrying.')
                    time.sleep(backoff)
                except Exception:
                    self.logger.error(traceback.format_exc())
                    backoff = min(90, 5 * (2 ** i)) + random.uniform(0, 10)
                    time.sleep(backoff)

        self.logger.error(f'download failed: exhausted all {len(urls)} url(s) x {self._retry} attempt(s) '
                           f'for target {target_file_path}, none produced a valid file.')
        return False



# if __name__ == "__main__":
#     import logging
#     import subprocess

#     logging.basicConfig(
#         level=logging.INFO,
#         format="%(asctime)s %(levelname)s %(name)s - %(message)s"
#     )
#     logger = logging.getLogger("ipfs_test")

#     ipfs = IPFS(logger)

#     # folder you want to upload
#     current_dir = "./2026-04-15"

#     # create archive OUTSIDE that folder
#     archive_name = os.path.basename(current_dir) + ".tar.gz"
#     test_file = os.path.join("/tmp", archive_name)

#     # where to save downloaded file
#     download_file_path = "./download_test.tar.gz"

#     # must match uploaded filename
#     test_name = archive_name

#     print("Creating archive from:", current_dir)
#     subprocess.run(
#         ["tar", "-czf", test_file, "-C", current_dir, "."],
#         check=True
#     )

#     print("Uploading:", test_file)
#     cid = ipfs.upload(test_file)
#     print("CID:", cid)

#     if not cid:
#         print("Upload failed")
#         raise SystemExit(1)

#     urls = ipfs._get_url(cid, test_name)
#     print("URLs:")
#     for one_url in urls:
#         print(one_url)

#     print("Downloading to:", download_file_path)
#     ok = ipfs.download(urls, download_file_path)
#     print("Download ok:", ok)

#     if ok and os.path.exists(download_file_path):
#         print("Downloaded size:", os.stat(download_file_path).st_size)