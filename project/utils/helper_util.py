import os
import json
import random
import time
import traceback
from flask import jsonify

from project.extensions import app_config


def response(code_msg, data=[]):
    code, msg = code_msg.value
    return jsonify({'errcode': code, 'errmsg': msg, 'data': data, 'version': app_config.APP_VERSION})


def download_ipfs_file(ipfs, data_dir, file_id, file_name, logger, tarutil, times=3):
    # Every node watching the chain notices a new/updated proposal within
    # about the same 1s poll window and, without this, would all start
    # downloading the same file at once - the retry/backoff spacing inside
    # IPFS.download() only spreads out RETRIES, it can't undo an initial
    # wave that's already synchronized. A random head start before the
    # first attempt spreads that initial wave out too.
    head_start = random.uniform(0, 45)
    logger.info(f'download_ipfs_file: waiting {head_start:.1f}s head start before first attempt for {file_name}.')
    time.sleep(head_start)
    logger.info('download file id: {}'.format(file_id))
    tar_file_name = os.path.join(data_dir, file_name)
    ipfs_urls = ipfs._get_url(file_id, file_name)
    logger.info(f'download_ipfs_file: {file_name}, {len(ipfs_urls)} url(s) x {times} pass(es): {ipfs_urls}')
    for pass_num, url in enumerate(ipfs_urls * times):  # try {times} times
        try:
            if ipfs.download(url, tar_file_name):
                try:
                    tarutil.untar(tar_file_name, path=tar_file_name[:-7])
                except Exception:
                    # Downloaded fine, but the archive itself didn't extract -
                    # distinct from a download failure, so log it as such
                    # rather than folding it into the generic warning below.
                    logger.warning(f'download ipfs {file_name}: downloaded ok but untar failed, '
                                    f'url: {url}, exception: {traceback.format_exc()}')
                    continue
                logger.info(f'download ipfs {file_name} data ok.')
                return True
            else:
                logger.warning(f'download ipfs {file_name}: attempt {pass_num + 1}/{len(ipfs_urls) * times} '
                                f'failed (no valid file from this url), url: {url}')
        except Exception:
            logger.warning('download from url: {} failed, exception: {}'.format(url, traceback.format_exc()))
    # Cooldown before returning control to the caller: IPFS.download() already
    # backs off between its own internal retries, but once this whole
    # function gives up, the caller (data_job's main loop) is otherwise free
    # to immediately call it again on the next iteration - across ~20 nodes
    # doing that at once, a hard failure here would just re-trigger the same
    # gateway pressure a few seconds later instead of actually cooling off.
    cooldown = random.uniform(30, 90)
    logger.error(f'download_ipfs_file: {file_name} failed - exhausted all {len(ipfs_urls)} url(s) x {times} '
                 f'pass(es), giving up. Cooling down {cooldown:.1f}s before returning to caller.')
    time.sleep(cooldown)
    return False


def reset_block_number_file(block_number_path, logger=None):
    try:
        with open(block_number_path, 'r') as rf:
            data = rf.read()
            if logger:
                logger.info('path: {}, info: {}'.format(block_number_path, data))
            bn_data = json.loads(data)
        if bn_data and bn_data.get('is_run'):
            bn_data['is_run'] = False
            with open(block_number_path, 'w') as wf:
                json.dump(bn_data, wf)
    except:
        if logger:
            logger.error(traceback.format_exc())
