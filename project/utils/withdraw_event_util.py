import contextlib
import datetime
import fcntl
import json
import logging
import os
import re
import time

from web3 import Web3

from project.utils.cache_util import CacheUtil
from project.utils.data_util import SaveData
from project.utils.date_util import timestamp_to_format2

# Every WithdrawToken event on the incentive contract pays out LUCA.
LUCA_COIN_ADDRESS = '0x51E6Ac1533032E72e92094867fD5921e3ea1bfa0'
LOG_QUERY_INTERVAL = 5000
# del_old_datas_job removes every prefetching_events entry that sorts before
# 'data_<old date>', so these must sort after 'data_' to survive it. AssetsService
# subtracts every withdrawal line in every plain file there (skipping
# directories), so files holding withdrawal items are staged in a sub-directory.
LOCK_FILE_NAME = 'lock_withdraw_events'
CHECK_CURSOR_FILE_NAME = 'withdraw_check_block.json'
STAGING_DIR_NAME = 'temp_file_staging'
_END_BLOCK_FILE_RE = re.compile(r'^data_(\d{4}-\d{2}-\d{2})_end_block\.txt$')
_logger = logging.getLogger('withdraw_check')


def withdraw_key(address, nonce):
    # The contract tracks each withdrawal by (user, nonce) - withdrawAmounts(addr,
    # nonce) - and the reduction, temp_file names and the ledger all key on it
    # too. A transaction hash is not unique per withdrawal: one transaction
    # (e.g. through a batching contract) can emit several WithdrawToken events.
    return '{}_{}'.format(address.lower(), int(nonce))


def event_key(event):
    return withdraw_key(event['args']['_userAddr'], event['args']['_nonce'])


def item_key(item):
    return withdraw_key(item['address'], item['nonce'])


def event_to_item(event):
    return {
        'address': event['args']['_userAddr'].lower(),
        'nonce': event['args']['_nonce'],
        'amount': str(Web3.fromWei(event['args']['_amount'], 'ether')),
        'hash_value': event['transactionHash'].hex(),
        'block_number': event['blockNumber'],
        'coin_address': LUCA_COIN_ADDRESS,
        'coin_type': 'luca'
    }


def recorded_keys(data_file):
    keys = set()
    if not os.path.exists(data_file):
        return keys
    with open(data_file, 'r') as rf:
        for line in rf:
            if not line.strip():
                continue
            try:
                keys.add(item_key(json.loads(line)))
            except (ValueError, KeyError, TypeError):
                # e.g. a half-written line left by a killed process. Skipping it
                # keeps the prefetch job (which calls this every run) working;
                # failing here would stop it recording any withdrawal at all.
                _logger.error('unreadable line in {}, skipping it: {!r}'.format(data_file, line[:200]))
    return keys


@contextlib.contextmanager
def withdraw_events_lock(p_event_data_dir):
    """Serializes access to the day files, temp_file and the check cursor
    between the prefetch job, withdraw_check_job and the data job. flock locks
    belong to the open file, so this also excludes other threads of the same
    scheduler process."""
    with open(os.path.join(p_event_data_dir, LOCK_FILE_NAME), 'a') as lf:
        fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lf.fileno(), fcntl.LOCK_UN)


@contextlib.contextmanager
def withdraw_events_read_lock(p_event_data_dir, timeout):
    """Shared lock for readers that must not hang (an HTTP request): waits up
    to timeout seconds for writers to finish, then yields whether it got the
    lock. Readers holding it don't block each other."""
    with open(os.path.join(p_event_data_dir, LOCK_FILE_NAME), 'a') as lf:
        deadline = time.time() + timeout
        locked = False
        while True:
            try:
                fcntl.flock(lf.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
                locked = True
                break
            except BlockingIOError:
                if time.time() >= deadline:
                    break
                time.sleep(0.05)
        try:
            yield locked
        finally:
            if locked:
                fcntl.flock(lf.fileno(), fcntl.LOCK_UN)


def _replace_file(p_event_data_dir, target_path, content):
    # write in the staging dir and move into place whole, so no reader ever
    # sees a half-written file
    staging_dir = os.path.join(p_event_data_dir, STAGING_DIR_NAME)
    os.makedirs(staging_dir, exist_ok=True)
    staging_path = os.path.join(staging_dir, os.path.basename(target_path))
    with open(staging_path, 'w') as wf:
        json.dump(content, wf)
    os.replace(staging_path, target_path)


def write_temp_file(p_event_data_dir, item):
    # prefetching_chain_job sends every file in temp_file to the ledger
    temp_dir = os.path.join(p_event_data_dir, 'temp_file')
    os.makedirs(temp_dir, exist_ok=True)
    _replace_file(p_event_data_dir, os.path.join(temp_dir, '{}_{}.txt'.format(item['address'], item['nonce'])), item)


def _shift_date(date, days):
    return (datetime.datetime.strptime(date, '%Y-%m-%d') + datetime.timedelta(days=days)).strftime('%Y-%m-%d')


def belong_date(timestamp, logger):
    # the exact rule the prefetch job's SaveData uses to pick an event's day file
    return SaveData(None, [], '', 'data', 0, 0, 0, logger)._get_belong_date(None, timestamp)[0]


def _recorded_keys_around(p_event_data_dir, date):
    # an event already filed under a neighbouring day must not be added to this one
    keys = set()
    for d in (_shift_date(date, -1), date, _shift_date(date, 1)):
        keys |= recorded_keys(os.path.join(p_event_data_dir, 'data_{}.txt'.format(d)))
    return keys


def day_end_block(p_event_data_dir, date):
    path = os.path.join(p_event_data_dir, 'data_{}_end_block.txt'.format(date))
    if not os.path.exists(path):
        return None
    with open(path, 'r') as rf:
        return json.load(rf)['block']


def latest_day_end_block(p_event_data_dir):
    # end block of the most recently closed day, i.e. where the open day starts
    dates = [m.group(1) for m in (_END_BLOCK_FILE_RE.match(f) for f in os.listdir(p_event_data_dir)) if m]
    return day_end_block(p_event_data_dir, max(dates)) if dates else None


def approved_date(web3eth):
    """The pagerank date of the latest approved snapshot proposal, read from
    the chain - same rule AssetsService uses. A local day folder isn't enough:
    the data job writes it before the vote, so it exists for a failed day too."""
    from project.extensions import app_config
    proposal_time = web3eth.get_latest_success_snapshoot_proposal()[5]
    proposal_datetime = timestamp_to_format2(proposal_time)
    if proposal_datetime > '{} {}:{}:00'.format(proposal_datetime[:10], app_config.START_HOUR,
                                                 app_config.START_MINUTE):
        return proposal_datetime[:10]
    return timestamp_to_format2(proposal_time, timedeltas={'days': 1}, opera=-1)[:10]


def approved_end_block(web3eth, data_dir, p_event_data_dir):
    """End block of the latest approved day - its deductions are final, so
    nothing up to here needs checking. None when this node doesn't know it."""
    date = approved_date(web3eth)
    block = day_end_block(p_event_data_dir, date)
    if block is not None:
        return block
    snapshot_path = os.path.join(data_dir, date, CacheUtil._PREFETCHING_EVENT_BLOCK_NUMBER_FILE_NAME)
    if os.path.exists(snapshot_path):
        with open(snapshot_path, 'r') as rf:
            return json.load(rf)['block']
    return None


def prefetch_cursor(p_event_data_dir):
    # the last block the prefetch job has fully processed
    path = os.path.join(p_event_data_dir, 'block_number.txt')
    if not os.path.exists(path):
        return None
    with open(path, 'r') as rf:
        return json.load(rf).get('block')


def check_cursor(p_event_data_dir):
    # the last block withdraw checking has fully covered
    path = os.path.join(p_event_data_dir, CHECK_CURSOR_FILE_NAME)
    if not os.path.exists(path):
        return None
    with open(path, 'r') as rf:
        return json.load(rf).get('block')


def append_to_day_files(p_event_data_dir, items, logger):
    """Append items (each with '_time') to the day file their timestamp belongs
    to - the same files and rule as the prefetch job's SaveData. Pure file I/O,
    so callers can run it while holding withdraw_events_lock without making it
    wait on an RPC. Returns {date: [items]}."""
    by_date = {}
    for item in items:
        by_date.setdefault(belong_date(item['_time'], logger), []).append(item)
    for date, date_items in by_date.items():
        with open(os.path.join(p_event_data_dir, 'data_{}.txt'.format(date)), 'a') as wf:
            for item in date_items:
                wf.write('{}\n'.format(json.dumps(item)))
    return by_date


def advance_check_cursor(p_event_data_dir, block):
    # only ever moves forward, so an older or repeated run can't move it back
    with withdraw_events_lock(p_event_data_dir):
        current = check_cursor(p_event_data_dir)
        if current is None or block > current:
            _replace_file(p_event_data_dir, os.path.join(p_event_data_dir, CHECK_CURSOR_FILE_NAME),
                          {'block': block, 'updated_at': int(time.time())})


def reconcile_withdraw_events(web3eth, p_event_data_dir, start_block, end_block, logger):
    """Record every WithdrawToken event in (start_block, end_block] that the
    prefetch job missed.

    Each missed event is appended to the day file its block timestamp belongs to
    (which the data job's reduction reads) and to temp_file (which the
    prefetching chain job sends to the ledger). Returns {'found', 'healed',
    'skipped'}; an event is skipped when its block timestamp can't be read, and
    the caller then leaves the range to be read again.
    """
    found = {}
    for start in range(start_block + 1, end_block + 1, LOG_QUERY_INTERVAL):
        end = min(start + LOG_QUERY_INTERVAL - 1, end_block)
        for event in web3eth.get_incentive_events(start, end):
            found.setdefault(event_key(event), event)
    logger.info('withdraw reconcile: {} event(s) in blocks {}-{} via {}'.format(
        len(found), start_block + 1, end_block, web3eth.rpc_name()))

    # timestamps are fetched before taking the lock so it's held only for file writes
    items_by_date = {}
    skipped = 0
    block_timestamps = {}
    recorded_by_date = {}
    for event in sorted(found.values(), key=lambda e: (e['blockNumber'], e['logIndex'])):
        item = event_to_item(event)
        block_number = item['block_number']
        if block_number not in block_timestamps:
            block_info = web3eth.get_block_by_number(block_number)
            block_timestamps[block_number] = block_info['timestamp'] if block_info else None
        if block_timestamps[block_number] is None:
            skipped += 1
            logger.info('withdraw reconcile: no timestamp for block {}, leaving {} for a later run.'.format(
                block_number, item['hash_value']))
            continue
        item['_time'] = block_timestamps[block_number]
        date = belong_date(item['_time'], logger)
        if date not in recorded_by_date:
            recorded_by_date[date] = _recorded_keys_around(p_event_data_dir, date)
        if item_key(item) not in recorded_by_date[date]:
            items_by_date.setdefault(date, []).append(item)

    healed = []
    if items_by_date:
        with withdraw_events_lock(p_event_data_dir):
            for date, items in sorted(items_by_date.items()):
                # the prefetch job may have recorded some of these since the read above
                recorded = _recorded_keys_around(p_event_data_dir, date)
                new_items = [item for item in items if item_key(item) not in recorded]
                if not new_items:
                    continue
                append_to_day_files(p_event_data_dir, new_items, logger)
                for item in new_items:
                    write_temp_file(p_event_data_dir, item)
                healed.extend(new_items)
                logger.info('withdraw reconcile: healed {} missed event(s) for {}: {}'.format(
                    len(new_items), date,
                    ['{}/{}/{}'.format(i['block_number'], i['address'], i['amount']) for i in new_items]))
    if not healed:
        logger.info('withdraw reconcile: all {} event(s) already recorded.'.format(len(found) - skipped))
    return {'found': len(found), 'healed': healed, 'skipped': skipped}
