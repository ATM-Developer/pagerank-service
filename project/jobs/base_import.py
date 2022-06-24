import os
import time
import json
import fcntl
import shutil
import logging
import traceback
from web3 import Web3
from decimal import Decimal
from project.extensions import scheduler, app_config
from concurrent.futures import ThreadPoolExecutor, wait, ALL_COMPLETED

from project.utils.date_util import time_format, get_pagerank_date, get_previous_pagerank_date, datetime_to_timestamp, \
    get_now_timestamp, timestamp_to_format2, get_dates_list
from project.utils.eth_util import Web3Eth, check_vote, PrivateChain2
from project.utils.settings_util import get_cfg, get_str, get_int
from project.utils.coin_util import get_coin_list, check_haved_earnings
from project.utils.cache_util import CacheUtil
from project.utils.tar_util import TarUtil
from project.utils.helper_util import download_ipfs_file, reset_block_number_file
from project.utils.data_util import SaveData
from project.models.enums import EarningsType
from project.services.ipfs_service import IPFS
from project.services.blockchain_service import get_yesterday_file_id

lock_file_dir_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'lock_file')
if not os.path.exists(lock_file_dir_path):
    try:
        os.makedirs(lock_file_dir_path)
    except:
        pass
data_dir = get_cfg('setting', 'data_dir', path_join=True)
