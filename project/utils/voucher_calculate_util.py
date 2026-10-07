# -*- encoding: utf-8 -*-

import os
import json
import logging
import traceback
from decimal import Decimal
from collections import OrderedDict, defaultdict

from project.extensions import app_config
from project.utils.settings_util import get_cfg
from project.utils.date_util import get_pagerank_date
from project.utils.cache_util import CacheUtil
from project.utils.value_util import _truncate_earnings
from project.configs.voucher.voucher_config import VOUCHER_REWARD_GROUPS, VOUCHER_GROUP_ALGOS

_VOUCHER_EVENT_KEYS = ('CHAIN', 'ADDRESS', 'ABI', 'FIRST_BLOCK', 'LAUNCH_DATE')


def configured_voucher_events(logger=None):
    events = getattr(app_config, 'EVENTS', {}) or {}
    names = []
    for event_name in getattr(app_config, 'VOUCHER_DATA_EVENTS', []) or []:
        event_cfg = events.get(event_name) or {}
        missing = [k for k in _VOUCHER_EVENT_KEYS if k not in event_cfg]
        if missing:
            if logger:
                logger.warning("voucher event '{}' skipped: EVENTS entry missing {}".format(event_name, missing))
            continue
        names.append(event_name)
    return names


def launched_voucher_events(pagerank_date, logger=None):
    events = app_config.EVENTS
    return [e for e in configured_voucher_events(logger) if pagerank_date >= events[e]['LAUNCH_DATE']]


def voucher_end_block_path(data_dir, event_name, pagerank_date):
    return os.path.join(data_dir, event_name, 'data_{}_end_block.txt'.format(pagerank_date))


def _find_reward_group(voucher_type, mode):
    for group in VOUCHER_REWARD_GROUPS:
        if group['mode'] == mode and voucher_type in (group.get('voucher_types') or []):
            return group
    return None


def _validate_coin_totals(nested, group_name):
    if not isinstance(nested, dict):
        raise TypeError("algo for group '{}' must return a dict, got {}".format(group_name, type(nested).__name__))
    for coin, totals in nested.items():
        if not isinstance(coin, str) or not coin:
            raise TypeError("algo for group '{}' returned a non-coin key: {!r}".format(group_name, coin))
        if not isinstance(totals, dict):
            raise TypeError("algo for group '{}' coin '{}' must map to a dict, got {}".format(
                group_name, coin, type(totals).__name__))
        for address, amount in totals.items():
            if not isinstance(address, str) or not address:
                raise TypeError("algo for group '{}' returned a non-address key: {!r}".format(group_name, address))
            if not isinstance(amount, (int, Decimal)):
                raise TypeError("algo for group '{}' returned a non-numeric amount for {}: {!r}".format(
                    group_name, address, amount))


def _validate_pool(pool, group_name):
    if not isinstance(pool, dict):
        raise TypeError("pool for group '{}' must be a dict, got {}".format(group_name, type(pool).__name__))
    for coin, amount in pool.items():
        if not isinstance(coin, str) or not coin:
            raise TypeError("pool for group '{}' returned a non-coin key: {!r}".format(group_name, coin))
        if not isinstance(amount, (int, Decimal)):
            raise TypeError("pool for group '{}' coin '{}' must be numeric, got {!r}".format(
                group_name, coin, amount))


class ToCalculate:
    def __init__(self):
        self.data_dir = get_cfg('setting', 'data_dir', path_join=True)
        self.cache_util = CacheUtil()
        self.logger = logging.getLogger('voucher_incentive_calculate')

    def _load_today_records(self, pagerank_date):
        records = []
        seen = set()
        for event_name in configured_voucher_events(self.logger):
            data_file_path = os.path.join(self.data_dir, event_name, 'data_{}.txt'.format(pagerank_date))
            if not os.path.exists(data_file_path):
                continue
            with open(data_file_path, 'r') as rf:
                for line in rf.readlines():
                    if line.strip():
                        record = json.loads(line.strip())
                        key = (record.get('chain'), record.get('transaction_hash'), record.get('log_index'))
                        if key in seen:
                            continue
                        seen.add(key)
                        records.append(record)
        return records

    def _load_end_blocks(self, pagerank_date):
        end_blocks = {}
        for event_name in launched_voucher_events(pagerank_date, self.logger):
            with open(voucher_end_block_path(self.data_dir, event_name, pagerank_date), 'r') as rf:
                end_blocks[event_name] = json.load(rf)['block']
        return end_blocks

    def calculate(self):
        pagerank_date = get_pagerank_date()
        records = self._load_today_records(pagerank_date)
        self.cache_util.save_voucher_incentive_block_number(self._load_end_blocks(pagerank_date))
        balances = self.cache_util.get_yesterday_voucher_points_balance()
        by_type = defaultdict(list)
        for r in records:
            by_type[r['voucher_type']].append(r)
        modes = {int(vt): b['mode'] for vt, b in balances.items()}
        for voucher_type, type_records in by_type.items():
            modes[voucher_type] = type_records[0]['mode']
        if not modes:
            self.logger.info('no voucher_incentive records or balances for {}, saving empty results'
                             .format(pagerank_date))
            self.cache_util.save_voucher_pr({})
            self.cache_util.save_voucher_reward({})
            self.cache_util.save_voucher_points_balance({})
            self.cache_util.add_extra_luca('voucher', {})
            self.cache_util.save_voucher_reward_total([])
            return True
        pr_result = OrderedDict()
        reward_result = OrderedDict()
        new_balances = {}
        combined = defaultdict(lambda: defaultdict(Decimal))
        extra_coins = defaultdict(Decimal)
        for voucher_type in sorted(modes):
            type_records = by_type.get(voucher_type, [])
            mode = modes[voucher_type]
            carried = {coin: {address: Decimal(amount) for address, amount in addr_amounts.items()}
                       for coin, addr_amounts in balances.get(str(voucher_type), {}).get('coins', {}).items()}
            group = _find_reward_group(voucher_type, mode)
            algo = VOUCHER_GROUP_ALGOS.get(group['name']) if group else None
            if algo is None:
                self.logger.info('voucherType {} mode {} is not configured{}, ignoring {} record(s)'.format(
                    voucher_type, mode, '' if group is None else ' with an algo (group {!r})'.format(group['name']),
                    len(type_records)))
                continue
            default_coin = group['coin']
            pr_func, pool_func, reward_func = algo
            available = None
            try:
                pr_totals = pr_func(type_records, default_coin) if type_records else {}
                _validate_coin_totals(pr_totals, group['name'] + ' (pr)')
                available = defaultdict(lambda: defaultdict(Decimal))
                for source in (carried, pr_totals):
                    for coin, addr_amounts in source.items():
                        for address, amount in addr_amounts.items():
                            available[coin][address] += amount
                claims = {coin: {a: v for a, v in addr_amounts.items() if v > 0}
                          for coin, addr_amounts in available.items()}
                pool = pool_func(type_records, default_coin)
                if default_coin is not None:
                    pool = pool if pool else pool_func([], default_coin)
                _validate_pool(pool, group['name'] + ' (pool)')
                reward_totals = reward_func(claims, pool, default_coin)
                _validate_coin_totals(reward_totals, group['name'] + ' (reward)')
                reward_totals = {coin: {address: _truncate_earnings(amount, app_config.EARNINGS_ACCURACY)
                                        for address, amount in addr_amounts.items()}
                                 for coin, addr_amounts in reward_totals.items()}
                reward_totals = self._cap_to_claims(reward_totals, claims)
            except Exception:
                self.logger.error('algo for group {!r} (voucherType {}) failed validation, skipping:\n{}'.format(
                    group['name'], voucher_type, traceback.format_exc()))
                pr_result[voucher_type] = {}
                reward_result[voucher_type] = {}
                self._keep_balance(new_balances, voucher_type, mode, available if available is not None else carried)
                continue
            left = {coin: dict(addr_amounts) for coin, addr_amounts in available.items()}
            for coin, addr_amounts in reward_totals.items():
                for address, amount in addr_amounts.items():
                    left.setdefault(coin, {})
                    left[coin][address] = left[coin].get(address, Decimal(0)) - amount
            self._keep_balance(new_balances, voucher_type, mode, left)
            pr_result[voucher_type] = {
                coin: {address: str(amount) for address, amount in addr_amounts.items()}
                for coin, addr_amounts in pr_totals.items()
            }
            reward_result[voucher_type] = {
                coin: {address: str(amount) for address, amount in addr_amounts.items()}
                for coin, addr_amounts in reward_totals.items()
            }
            for coin, addr_amounts in reward_totals.items():
                for address, amount in addr_amounts.items():
                    combined[coin][address] += amount
            for coin, coin_pool in pool.items():
                coin_paid = sum(reward_totals.get(coin, {}).values(), Decimal(0))
                extra_coins[coin] += max(Decimal(str(coin_pool)) - coin_paid, Decimal(0))
            self.logger.info('voucherType {}: {} claim(s), carried in {} address(es), carried out {} address(es)'
                             .format(voucher_type, sum(len(v) for v in claims.values()),
                                     sum(len(v) for v in carried.values()),
                                     sum(len(v) for v in new_balances.get(str(voucher_type), {})
                                         .get('coins', {}).values())))
        self.cache_util.save_voucher_pr(pr_result)
        self.cache_util.save_voucher_reward(reward_result)
        self.cache_util.save_voucher_points_balance(new_balances)
        extra_coins = {coin: _truncate_earnings(amount, app_config.EARNINGS_ACCURACY)
                       for coin, amount in extra_coins.items()}
        extra = self.cache_util.add_extra_luca('voucher', extra_coins)
        self.logger.info('voucher extra: added {}, voucher extra balance {}.'
                         .format(extra_coins, extra.get('voucherExtra')))
        earnings_datas = []
        for coin, addr_amounts in combined.items():
            for address, amount in addr_amounts.items():
                if amount == 0:
                    continue
                earnings_datas.append({'address': address, 'amount': str(amount), 'coin': coin})
        self.cache_util.save_voucher_reward_total(earnings_datas)
        if earnings_datas:
            self.logger.info('voucher_incentive: {} earnings entrie(s) across {} coin(s) for {}'.format(
                len(earnings_datas), len(combined), pagerank_date))
        else:
            self.logger.info('voucher_incentive: no net earnings deltas for {}'.format(pagerank_date))
        return True

    @staticmethod
    def _cap_to_claims(reward_totals, claims):
        return {coin: {address: min(amount, claims.get(coin, {}).get(address, Decimal(0)))
                       for address, amount in addr_amounts.items()}
                for coin, addr_amounts in reward_totals.items()}

    @staticmethod
    def _keep_balance(new_balances, voucher_type, mode, coins):
        kept = {coin: {address: str(amount) for address, amount in addr_amounts.items() if amount != 0}
                for coin, addr_amounts in coins.items()}
        kept = {coin: addr_amounts for coin, addr_amounts in kept.items() if addr_amounts}
        if kept:
            new_balances[str(voucher_type)] = {'mode': mode, 'coins': kept}

    def run(self):
        try:
            self.logger.info('Calculating voucher_incentive...')
            success = self.calculate()
            self.logger.info('Done' if success else 'Failed')
        except:
            self.logger.error(traceback.format_exc())
