import os
import json
import traceback
from flask import jsonify


def response(code_msg, data=[]):
    code, msg = code_msg.value
    return jsonify({'errcode': code, 'errmsg': msg, 'data': data})


def download_ipfs_file(ipfs, data_dir, file_id, file_name, logger, tarutil, times=3):
    logger.info('download file id: {}'.format(file_id))
    tar_file_name = os.path.join(data_dir, file_name)
    ipfs_urls = ipfs._get_url(file_id, file_name)
    for url in ipfs_urls * times:  # try {times} times for each url
        try:
            if ipfs.download(url, tar_file_name):
                tarutil.untar(tar_file_name, path=tar_file_name[:-7])
                logger.info(f'download ipfs {file_name} data ok.')
                return True
        except:
            logger.error(traceback.format_exc())
    return False


def reset_block_number_file(block_number_path):
    try:
        with open(block_number_path, 'r') as rf:
            bn_data = json.load(rf)
        if bn_data and bn_data.get('is_run'):
            bn_data['is_run'] = False
            with open(block_number_path, 'w') as wf:
                json.dump(bn_data, wf)
    except:
        pass
