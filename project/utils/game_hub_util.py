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
    """Like Web3.fromWei, but allows negative input (getDailyUserPoints is int256)."""
    with localcontext() as ctx:
        ctx.prec = 999
        return Decimal(points_wei, context=ctx) / _WEI_PER_ETHER


def _date_key_to_calendar_date(date_key, start_offset, day_length):
    """Converts a dateKey to its real UTC calendar date, since an instance's
    round length may be shorter than 24h."""
    ts = start_offset + date_key * day_length
    return datetime.datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d')


def _retry(func, logger, times=3, reconnect=None):
    """Retries transient errors; a contract revert is deterministic so it's
    raised immediately. reconnect, if given, rotates to a different endpoint
    between attempts."""
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
    """Ranks RPCs by latest block number so the caller can prefer the most
    in-sync endpoint; unreachable ones are dropped rather than ranked last."""
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
    """Read-only client for the AGF DailyGame GameHub + DailySessionManager contracts."""

    def __init__(self, logger, chain='binance'):
        self.logger = logger
        self.chain_config = app_config.CHAINS[chain]
        self._used_uris = []
        # One retry per configured endpoint, so a reconnect rotation can
        # exhaust the whole RPC list before giving up.
        self._retry_times = max(1, len(self.chain_config['web3_provider_uri']))
        self._connect()

    def _connect(self):
        """Ranks all configured endpoints and connects to the best untried
        one; the rotation resets once every endpoint's been tried, so a
        transient outage recovers instead of sticking on a fallback."""
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

    def fetch_instance_day(self, instance_address, since_date_key=None, on_date_done=None, known_calendar_dates=None):
        """Fetches per-staker points for one instance, from since_date_key
        (the persisted cursor; None scans the full BOOST_LOOKBACK_DAYS window,
        clamped to BOOST_START_DATE) up to but NOT including currentDateKey.

        currentDateKey is always the live, still-open round - given the
        boost cutoff (BOOST_START_HOUR/MINUTE) sits ~15min after GameHub's
        own round cutoff, currentDateKey stays the same round for this
        entire boost day's ~24h retry window and only rolls over right at
        the next boost day's cutoff. So it can never be safely counted no
        matter how late within that window a node happens to poll, and is
        excluded structurally (not just via dailyPointsFinalized, which
        would still be false most of the window but could flip true near
        the very end of it, right before rollover - counting it then would
        pull a round into the wrong boost day). dailyPointsFinalized is kept
        as a secondary check on top of that, in case even currentDateKey - 1
        hasn't settled on-chain yet for some reason; that dateKey is skipped
        entirely (not counted, not persisted) until it flips true on a later
        pass. Zero-point stakers are skipped since they can't contribute to
        any share.

        on_date_done(calendar_date, date_key, date_rows) fires per finalized
        dateKey so the caller can persist progress incrementally; date_key
        lets the caller replace (not accumulate) that dateKey's rows on a
        re-fetch.

        Returns (rows, earliest_calendar_date, last_finalized_date_key) - the
        cursor only advances through the leading run of confirmed-finalized
        dateKeys; the first not-yet-finalized one is left for next run.
        """
        start = time.time()
        # Rebuilt fresh per lambda (not captured once) so a reconnect() that
        # rotates self._w3 is actually picked up.
        current_date_key = _retry(lambda: self._session_manager(instance_address).functions.currentDateKey().call(),
                                  self.logger, times=self._retry_times, reconnect=self._connect)
        start_offset, day_length = _retry(
            lambda: self._session_manager(instance_address).functions.getSessionSchedule().call(),
            self.logger, times=self._retry_times, reconnect=self._connect)
        day_length = day_length or 86400
        lookback_days = getattr(app_config, 'BOOST_LOOKBACK_DAYS', 1)
        num_date_keys = max(1, lookback_days * 86400 // day_length)

        earliest_date_key = current_date_key - num_date_keys
        start_date = getattr(app_config, 'BOOST_START_DATE', None)
        if start_date:
            start_timestamp = datetime_to_timestamp('{} 00:00:00'.format(start_date))
            earliest_date_key = max(earliest_date_key, int((start_timestamp - start_offset) // day_length))
        if since_date_key is not None:
            # dailyPointsFinalized isn't guaranteed monotonic (a round can be
            # reset after the cursor advanced past it) - re-check here and
            # discard a cursor that's drifted ahead of what's actually
            # finalized on-chain, rather than trust it blindly.
            since_finalized = _retry(
                lambda: self._session_manager(instance_address).functions.dailyPointsFinalized(since_date_key).call(),
                self.logger, times=self._retry_times, reconnect=self._connect)
            if not since_finalized:
                self.logger.info('cursor dateKey {} for {} is not finalized on-chain - discarding cursor, '
                                 'rescanning from BOOST_START_DATE/BOOST_LOOKBACK_DAYS floor.'
                                 .format(since_date_key, instance_address))
                since_date_key = None
        if since_date_key is not None and known_calendar_dates is not None:
            # A finalized cursor can still sit downstream of an earlier hole
            # (e.g. a run that crashed mid-scan). Check every dateKey the
            # cursor would skip against history, and force a full rescan if
            # any calendar date in that range is missing, so it backfills.
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
                # Round hasn't settled on-chain yet - stakes can still change
                # mid-round, and different nodes would observe different
                # snapshots depending on exactly when they poll. Skip it
                # entirely (don't count it, don't persist it); it'll be
                # picked up once dailyPointsFinalized flips true.
                self.logger.info('dateKey {} for {} not finalized yet - skipping until a later pass.'
                                 .format(date_key, instance_address))
                cursor_still_consecutive = False
                continue
            date_rows = []
            seen_users = set()
            offset = 0
            while True:
                try:
                    users, _amounts, total = _retry(
                        lambda dk=date_key, off=offset: self._session_manager(instance_address).functions
                        .getDailyBoostStakes(dk, off, _BOOST_STAKES_PAGE_SIZE).call(),
                        self.logger, times=self._retry_times, reconnect=self._connect)
                except ContractLogicError as e:
                    self.logger.error('getDailyBoostStakes reverted for dateKey {}: {} - treating as no stakers'
                                       .format(date_key, e))
                    break
                for user in users:
                    # A retry between pages can land on a different (slightly
                    # out-of-sync) RPC, so the same wallet can appear twice -
                    # skip anything already counted this dateKey.
                    user_lower = user.lower()
                    if user_lower in seen_users:
                        continue
                    seen_users.add(user_lower)
                    points_wei = _retry(
                        lambda dk=date_key, u=user: self._session_manager(instance_address).functions
                        .dailyBoostStake(dk, u).call(),
                        self.logger, times=self._retry_times, reconnect=self._connect)
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
            rows.extend(date_rows)
            if on_date_done:
                on_date_done(_date_key_to_calendar_date(date_key, start_offset, day_length), date_key, date_rows)
            if cursor_still_consecutive:
                last_finalized_date_key = date_key
        earliest_calendar_date = _date_key_to_calendar_date(earliest_date_key, start_offset, day_length)
        self.logger.info('instance {} fetch took {:.2f}s, dateKeys {}-{} (currentDateKey {} excluded, still live), '
                         '{} rows'
                         .format(instance_address, time.time() - start, start_date_key, current_date_key - 1,
                                 current_date_key, len(rows)))
        return rows, earliest_calendar_date, last_finalized_date_key

    def fetch_all(self, memory=None, on_progress=None):
        """Fetches the rolling BOOST_LOOKBACK_DAYS window of per-player rows
        across every active operator's instance, resuming from memory
        (cursor + history per instance) instead of rescanning already-known
        days. memory of None fetches the full window fresh.

        on_progress(partial_memory), if given, fires per dateKey/instance so
        the caller can persist to disk incrementally instead of only at the
        very end.

        Returns (window_rows, updated_memory) for the caller to persist via
        CacheUtil.save_boost_memory.
        """
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

                def _on_date_done(calendar_date, date_key, date_rows, instance_history=instance_history):
                    # A not-yet-finalized dateKey returns full current state,
                    # not a delta - replace its prior rows rather than
                    # accumulate, or re-scans would double-count stakers.
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
