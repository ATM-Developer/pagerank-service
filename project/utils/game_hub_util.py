import time
import json
import datetime
import traceback
import requests
from decimal import Decimal, localcontext

from web3 import Web3
from web3.exceptions import ContractLogicError
from web3.middleware import geth_poa_middleware

from project.extensions import app_config
from project.configs.eth.eth_config import GAME_HUB_ABI, DAILY_SESSION_MANAGER_ABI
from project.utils.date_util import datetime_to_timestamp
from project.utils.logging_util import mask_rpc_url, mask_rpc_urls

_WEI_PER_ETHER = Decimal(10) ** 18
_BOOST_STAKES_PAGE_SIZE = 200
_RPC_RANK_TIMEOUT = 10


def _wei_to_ether(points_wei):
    with localcontext() as ctx:
        ctx.prec = 999
        return Decimal(points_wei, context=ctx) / _WEI_PER_ETHER


def _date_key_to_calendar_date(date_key, start_offset, day_length):
    ts = start_offset + date_key * day_length
    return datetime.datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d')


def _retry(func, logger, times=3, reconnect=None):
    last_exc = None
    for i in range(times):
        try:
            return func()
        except ContractLogicError:
            raise
        except Exception as e:
            last_exc = e
            logger.error('game hub call failed (attempt {}/{}): {}'.format(i + 1, times, e))
            if reconnect and i < times - 1:
                try:
                    reconnect()
                except Exception as reconnect_exc:
                    logger.error('game hub reconnect failed: {}'.format(reconnect_exc))
            time.sleep(2)
    raise last_exc


def _rank_uris_by_latest_block(rpc_urls, logger):
    data = {'jsonrpc': '2.0', 'method': 'eth_getBlockByNumber', 'params': ['latest', False], 'id': 1}
    ranked = []
    for url in rpc_urls:
        try:
            resp = requests.post(url, json=data, timeout=_RPC_RANK_TIMEOUT)
            number = int(json.loads(resp.text)['result']['number'][2:], 16)
            ranked.append((url, number))
        except Exception as e:
            logger.error('game hub rank failed for {}: {}'.format(mask_rpc_url(url), e))
    return sorted(ranked, key=lambda x: x[1], reverse=True)


class GameHubReader:
    def __init__(self, logger, chain='binance'):
        self.logger = logger
        self.chain_config = app_config.CHAINS[chain]
        self._used_uris = []
        self._retry_times = max(1, len(self.chain_config['web3_provider_uri']))
        self._connect()

    def _connect(self):
        rpc_urls = self.chain_config['web3_provider_uri']
        start = time.time()
        for attempt in range(10):
            ranked = _rank_uris_by_latest_block(rpc_urls, self.logger)
            if not ranked:
                self.logger.error('game hub connect attempt {}/10: no reachable web3_provider_uri yet, retrying.'
                                  .format(attempt + 1))
                continue
            if len(self._used_uris) >= len(ranked):
                self._used_uris = []
            for url, number in ranked:
                if url in self._used_uris:
                    continue
                self._used_uris.append(url)
                try:
                    w3 = Web3(Web3.HTTPProvider(url))
                    w3.eth.block_number
                    self.logger.info('game hub selected uri: {} (block {}), connect took {:.2f}s'
                                     .format(mask_rpc_url(url), number, time.time() - start))
                    self._w3 = w3
                    self._rebuild_contracts()
                    return
                except Exception as e:
                    self.logger.error('game hub uri failed: {}, {}'.format(mask_rpc_url(url), e))
        raise ConnectionError('no reachable web3_provider_uri after {:.2f}s: {}'
                              .format(time.time() - start, mask_rpc_urls(rpc_urls)))

    def _rebuild_contracts(self):
        try:
            self._w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        except Exception as e:
            if "You can't add the same un-named instance twice" not in str(e):
                raise
        self.hub = self._w3.eth.contract(address=Web3.toChecksumAddress(self.chain_config['GAME_HUB_ADDRESS']),
                                         abi=GAME_HUB_ABI)

    def _session_manager(self, instance_address):
        return self._w3.eth.contract(address=Web3.toChecksumAddress(instance_address),
                                     abi=DAILY_SESSION_MANAGER_ABI)

    def get_active_operators(self):
        return _retry(lambda: self.hub.functions.getActiveOperators().call(), self.logger,
                      times=self._retry_times, reconnect=self._connect)

    def get_instance(self, operator):
        return _retry(lambda: self.hub.functions.getInstance(operator).call(), self.logger,
                      times=self._retry_times, reconnect=self._connect)

    def _fetch_voucher_debits(self, instance_address, date_key):
        rows = []
        seen_users = set()
        offset = 0
        while True:
            try:
                users, amounts, total = _retry(
                    lambda dk=date_key, off=offset: self._session_manager(instance_address).functions
                    .getVoucherBoostDebits(dk, off, _BOOST_STAKES_PAGE_SIZE).call(),
                    self.logger, times=self._retry_times, reconnect=self._connect)
            except ContractLogicError as e:
                self.logger.error('getVoucherBoostDebits reverted for dateKey {}: {} - treating this dateKey as '
                                  'not fetchable this pass (not a real end-of-list signal).'
                                  .format(date_key, e))
                return rows, True
            for user, amount_wei in zip(users, amounts):
                user_lower = user.lower()
                if user_lower in seen_users:
                    continue
                seen_users.add(user_lower)
                if amount_wei == 0:
                    continue
                rows.append({
                    'dateKey': date_key,
                    'user': user_lower,
                    'points': str(_wei_to_ether(amount_wei)),
                })
            offset += len(users)
            if not users or offset >= total:
                break
        return rows, False

    def fetch_instance_day(self, instance_address, since_date_key=None, on_date_done=None, known_calendar_dates=None,
                           since_calendar_date=None):
        start = time.time()
        current_date_key = _retry(lambda: self._session_manager(instance_address).functions.currentDateKey().call(),
                                  self.logger, times=self._retry_times, reconnect=self._connect)
        start_offset, day_length = _retry(
            lambda: self._session_manager(instance_address).functions.getSessionSchedule().call(),
            self.logger, times=self._retry_times, reconnect=self._connect)
        day_length = day_length or 86400
        if since_date_key is None and since_calendar_date is not None:
            # Caller has no date_key cursor (e.g. boost_memory.json was
            # missing/reconstructed) but knows the most recent calendar_date
            # it already has locally-credited data for - resume just past
            # it instead of rescanning from BOOST_START_DATE.
            since_ts = datetime_to_timestamp('{} 00:00:00'.format(since_calendar_date))
            since_date_key = int((since_ts - start_offset) // day_length)
        start_date = getattr(app_config, 'BOOST_START_DATE', None)
        if start_date:
            start_timestamp = datetime_to_timestamp('{} 00:00:00'.format(start_date))
            earliest_date_key = int((start_timestamp - start_offset) // day_length)
        else:
            lookback_days = getattr(app_config, 'BOOST_LOOKBACK_DAYS', 1)
            num_date_keys = max(1, lookback_days * 86400 // day_length)
            earliest_date_key = current_date_key - num_date_keys
        if since_date_key is not None:
            since_finalized = _retry(
                lambda: self._session_manager(instance_address).functions.dailyPointsFinalized(since_date_key).call(),
                self.logger, times=self._retry_times, reconnect=self._connect)
            if not since_finalized:
                self.logger.info('cursor dateKey {} for {} is not finalized on-chain - discarding cursor, '
                                 'rescanning from BOOST_START_DATE/BOOST_LOOKBACK_DAYS floor.'
                                 .format(since_date_key, instance_address))
                since_date_key = None
        if since_date_key is not None and known_calendar_dates is not None:
            missing = [dk for dk in range(earliest_date_key, since_date_key + 1)
                      if dk >= 0 and _date_key_to_calendar_date(dk, start_offset, day_length)
                      not in known_calendar_dates]
            if missing:
                self.logger.info('{} calendar date(s) missing from history between BOOST_START_DATE and the '
                                 'cursor for {} - discarding cursor, rescanning from BOOST_START_DATE/'
                                 'BOOST_LOOKBACK_DAYS floor to backfill them.'
                                 .format(len(missing), instance_address))
                since_date_key = None
        start_date_key = earliest_date_key if since_date_key is None else max(since_date_key + 1, earliest_date_key)
        last_finalized_date_key = start_date_key - 1

        rows = []
        cursor_still_consecutive = True
        for date_key in range(start_date_key, current_date_key):
            if date_key < 0:
                continue
            finalized = _retry(
                lambda dk=date_key: self._session_manager(instance_address).functions.dailyPointsFinalized(dk).call(),
                self.logger, times=self._retry_times, reconnect=self._connect)
            if not finalized:
                self.logger.info('dateKey {} for {} not finalized yet - skipping until a later pass.'
                                 .format(date_key, instance_address))
                cursor_still_consecutive = False
                continue
            date_rows = []
            seen_users = set()
            offset = 0
            page_fetch_failed = False
            last_seen_total = None
            while True:
                try:
                    users, amounts, total = _retry(
                        lambda dk=date_key, off=offset: self._session_manager(instance_address).functions
                        .getDailyBoostStakes(dk, off, _BOOST_STAKES_PAGE_SIZE).call(),
                        self.logger, times=self._retry_times, reconnect=self._connect)
                except ContractLogicError as e:
                    self.logger.error('getDailyBoostStakes reverted for dateKey {}: {} - treating this dateKey as '
                                      'not fetchable this pass (not a real end-of-list signal).'
                                      .format(date_key, e))
                    page_fetch_failed = True
                    break
                last_seen_total = total
                for user, points_wei in zip(users, amounts):
                    user_lower = user.lower()
                    if user_lower in seen_users:
                        continue
                    seen_users.add(user_lower)
                    if points_wei == 0:
                        continue
                    date_rows.append({
                        'dateKey': date_key,
                        'user': user_lower,
                        'points': str(_wei_to_ether(points_wei)),
                    })
                offset += len(users)
                if not users or offset >= total:
                    break
            voucher_rows, voucher_fetch_failed = self._fetch_voucher_debits(instance_address, date_key)
            if page_fetch_failed or voucher_fetch_failed:
                self.logger.info('dateKey {} for {} could not be fully fetched this pass - skipping until a '
                                 'later pass, same as an unfinalized dateKey.'.format(date_key, instance_address))
                cursor_still_consecutive = False
                continue
            self.logger.info('dateKey {} for {}: {} stakers reported on-chain, {} stake rows, {} voucher debit '
                             'rows fetched.'
                             .format(date_key, instance_address, last_seen_total, len(date_rows), len(voucher_rows)))
            rows.extend(date_rows)
            if on_date_done:
                on_date_done(_date_key_to_calendar_date(date_key, start_offset, day_length), date_key, date_rows,
                            voucher_rows)
            if cursor_still_consecutive:
                last_finalized_date_key = date_key
        earliest_calendar_date = _date_key_to_calendar_date(earliest_date_key, start_offset, day_length)
        self.logger.info('instance {} fetch took {:.2f}s, dateKeys {}-{} (currentDateKey {} excluded, still live), '
                         '{} rows'
                         .format(instance_address, time.time() - start, start_date_key, current_date_key - 1,
                                 current_date_key, len(rows)))
        return rows, earliest_calendar_date, last_finalized_date_key

    def fetch_all(self, memory=None, on_progress=None):
        start = time.time()
        memory = memory or {}
        cursor = dict(memory.get('cursor') or {})
        history = {key: dict(date_keys) for key, date_keys in (memory.get('history') or {}).items()}
        window_rows = []
        operators = self.get_active_operators()
        self.logger.info('fetch_all: {} active operators'.format(len(operators)))
        for operator in operators:
            try:
                instance_address = self.get_instance(operator)
                if not instance_address or int(instance_address, 16) == 0:
                    self.logger.info('operator {} has no instance deployed - skipping.'.format(operator))
                    continue
                key = instance_address.lower()
                instance_history = history.setdefault(key, {})
                known_calendar_dates = set(instance_history.keys())

                def _on_date_done(calendar_date, date_key, date_rows, voucher_rows, instance_history=instance_history):
                    existing = [r for r in instance_history.get(calendar_date, []) if r.get('dateKey') != date_key]
                    existing.extend(date_rows)
                    instance_history[calendar_date] = existing
                    if on_progress:
                        on_progress({'cursor': cursor, 'history': history})

                _new_rows, earliest_calendar_date, last_finalized_date_key = self.fetch_instance_day(
                    instance_address, cursor.get(key), on_date_done=_on_date_done,
                    known_calendar_dates=known_calendar_dates)

                for calendar_date in [d for d in instance_history if d < earliest_calendar_date]:
                    del instance_history[calendar_date]

                for date_rows in instance_history.values():
                    window_rows.extend(date_rows)
                cursor[key] = last_finalized_date_key
                if on_progress:
                    on_progress({'cursor': cursor, 'history': history})
            except Exception:
                self.logger.error('operator {} fetch failed: {}'.format(operator, traceback.format_exc()))
        self.logger.info('fetch_all took {:.2f}s, {} rows across {} operators'
                         .format(time.time() - start, len(window_rows), len(operators)))
        return window_rows, {'cursor': cursor, 'history': history}
