from project.jobs.base_import import *
from project.utils.value_util import _round_decimal

logger = logging.getLogger('boost_pr')


_FALLBACK_LOOKBACK_DAYS = 30


def _most_recent_json(file_name, logger, start_days_back=1):
    for days_back in range(start_days_back, _FALLBACK_LOOKBACK_DAYS + 1):
        date = time_format(timedeltas={'days': days_back}, opera=-1)[:10]
        file_path = os.path.join(data_dir, date, file_name)
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                data = json.load(f)
            is_empty = not data or (isinstance(data, dict)
                                     and all(isinstance(v, dict) and not v for v in data.values()))
            if is_empty:
                logger.info('{} from {} exists but is still empty - continuing to fall back further.'
                            .format(file_name, date))
                continue
            logger.info('boost job falling back to {} from {}'.format(file_name, date))
            return data, date
    logger.info('no {} found in the last {} days'.format(file_name, _FALLBACK_LOOKBACK_DAYS))
    return {}, None


def _previous_pr(logger):
    return _most_recent_json(CacheUtil._PR_FILE_NAME, logger)


def _tier_floor(tier_caps):
    return min(Decimal(str(tier['min_share'])) for tier in tier_caps)


def _pr_eligible_addresses(prev_pr):
    tier_caps = app_config.BOOST_PR_TIER_CAPS
    floor = _tier_floor(tier_caps)
    return {addr.lower() for addr, share in prev_pr.get('MAINNET', {}).items() if Decimal(str(share)) >= floor}


def _eligible_rows(rows, prev_pr, logger=None):
    eligible = _pr_eligible_addresses(prev_pr)
    result = [row for row in rows if row['user'] in eligible]
    if logger:
        logger.info('eligibility filter: {} rows in, {} eligible ({} PR-eligible wallets in prev_pr).'
                    .format(len(rows), len(result), len(eligible)))
    return result


def _pr_tier_cap(share, tier_caps):
    for tier in tier_caps:
        if Decimal(str(tier['min_share'])) <= share < Decimal(str(tier['max_share'])):
            return Decimal(str(tier['max_points']))
    return None


def _check_pr_tier_range(rows, prev_pr, logger=None):
    tier_caps = app_config.BOOST_PR_TIER_CAPS
    shares = {addr.lower(): Decimal(str(share)) for addr, share in prev_pr.get('MAINNET', {}).items()}
    flagged = 0
    for row in rows:
        points = Decimal(str(row['points']))
        cap = _pr_tier_cap(shares.get(row['user'], Decimal(0)), tier_caps)
        if cap is not None and cap < points:
            flagged += 1
            if logger:
                logger.warning('boost row exceeds its PR-tier cap (the GameHub contract should have '
                               'prevented this): user {} points {} > tier cap {}.'
                               .format(row['user'], points, cap))
    if logger and flagged:
        logger.warning('pr tier check: {}/{} rows exceeded their tier cap.'.format(flagged, len(rows)))
    return rows


def _tier_ceiling(tier_caps):
    return max(Decimal(str(tier['max_points'])) for tier in tier_caps)


def _cap_backfill_rows(rows, logger=None):
    ceiling = _tier_ceiling(app_config.BOOST_PR_TIER_CAPS)
    capped = 0
    result = []
    for row in rows:
        points = Decimal(str(row['points']))
        if points > ceiling:
            capped += 1
            row = dict(row, points=str(ceiling))
        result.append(row)
    if logger and capped:
        logger.info('backfill tier cap: {}/{} rows exceeded the max tier ({}) - capped.'
                    .format(capped, len(rows), ceiling))
    return result


def _truncate_decimal(value, places):
    return _round_decimal(value, places)


def _ledger_debit_balances(cache_util, eligible_addresses, delta_date, logger=None):
    balances = {}
    for address in sorted(eligible_addresses):
        ledger = cache_util.get_boost_ledger(address)
        balances[address] = Decimal(str(ledger.get('point_balance', 0)))
    point_balance_total = sum(balances.values(), Decimal(0))
    range_start = cache_util.get_boost_ledger_fold_range_start(delta_date)
    range_total = Decimal(0)
    range_count = 0
    if range_start <= delta_date:
        for address, points in cache_util.get_boost_ledger_delta_range(range_start, delta_date, logger=logger).items():
            if address not in eligible_addresses:
                continue
            balances[address] = balances.get(address, Decimal(0)) + points
            range_total += points
            range_count += 1
    balances = {address: balance for address, balance in balances.items() if balance > 0}
    if logger:
        logger.info('ledger debit balances: point_balance total {} ({} wallets), range {} to {} adds {} '
                     '({} wallets) -> {}/{} eligible wallets carry a positive debit.'
                     .format(point_balance_total, len(eligible_addresses), range_start, delta_date, range_total,
                             range_count, len(balances), len(eligible_addresses)))
    return balances


def _compute_shares(user_points):
    total_points = sum(user_points.values())
    if total_points <= 0:
        return {}
    return {addr: str(_truncate_decimal(points / total_points, app_config.EARNINGS_ACCURACY))
            for addr, points in user_points.items() if points > 0}


def compute_wallet_boost_reward(share, pool):
    return _truncate_decimal(pool * share, app_config.EARNINGS_ACCURACY)


def _rebuild_boost_reward(cache_util, logger, pool):
    shares = cache_util.get_today_pr_boost().get('shares', {})
    reward_datas = []
    for address, share in shares.items():
        share = Decimal(str(share))
        if share <= 0 or pool == 0:
            continue
        reward = compute_wallet_boost_reward(share, pool)
        if reward == 0:
            continue
        reward_datas.append({'address': address, 'amount': str(reward)})
    cache_util.save_reward_boost(reward_datas)
    logger.info('rebuilt boost_reward.json against pool {} - {} wallets.'.format(pool, len(reward_datas)))


def _carve_out_boost_reward(cache_util, logger):
    day_amount = cache_util.get_today_day_amount()
    boost_reward = Decimal(str(day_amount.get('boost_reward', 0)))
    logger.info('boost_reward sourced from day_amount: {}'.format(boost_reward))

    try:
        prior_boost_day_amount = cache_util.get_today_boost_day_amount()
    except FileNotFoundError:
        prior_boost_day_amount = {}
    already_had_reward = 'boost_reward' in prior_boost_day_amount
    if already_had_reward and Decimal(str(prior_boost_day_amount['boost_reward'])) == boost_reward:
        return
    if already_had_reward:
        logger.info('boost_reward changed ({} -> {}) since the last pass - rebuilding boost_reward.json.'
                    .format(prior_boost_day_amount['boost_reward'], boost_reward))

    day_amount['boost_reward'] = str(boost_reward)
    cache_util.save_boost_day_amount(day_amount)
    luca_amount = cache_util.get_today_luca_amount()
    luca_amount['boostReward'] = str(boost_reward)
    cache_util.save_boost_luca_amount(luca_amount)
    if already_had_reward:
        _rebuild_boost_reward(cache_util, logger, boost_reward)


class CalculateBoost():
    def __init__(self):
        self.today_date = get_pagerank_date(app_config.BOOST_START_HOUR, app_config.BOOST_START_MINUTE)
        self.web3eth = Web3Eth(logger)
        self.cache_util = CacheUtil(hour=app_config.BOOST_START_HOUR, minute=app_config.BOOST_START_MINUTE)

    def main(self):
        times = 1
        while True:
            try:
                start_timestamp = get_now_timestamp()
                logger.info('calculate boost times: {}, time: {}'.format(times, start_timestamp))
                node_result = self.web3eth.is_senators_or_executer()
                logger.info('self address is : {}'.format(node_result))
                if not node_result:
                    if self.web3eth.check_vote() == 1:
                        return True
                    else:
                        time.sleep(5)
                        continue
                logger.info('calculate boost shares.')
                ready_date = self.cache_util.get_boost_memory().get('ready_date')
                if ready_date != self.today_date:
                    logger.info('boost_memory_job has not completed a full pass for {} yet (last: {}) '
                                '- retrying shortly.'.format(self.today_date, ready_date))
                    time.sleep(5)
                    continue
                prev_pr, pr_source_date = _previous_pr(logger)
                if pr_source_date is None:
                    logger.info('no pr.json available yet - retrying shortly instead of '
                                'finalizing a false zero-point pass.')
                    time.sleep(5)
                    continue
                self.cache_util.save_boost_pr_source(prev_pr, pr_source_date)
                logger.info('saved boost_pr_source.json (source_date={})'.format(pr_source_date))
                eligible_addresses = _pr_eligible_addresses(prev_pr)
                logger.info('eligible addresses count: {}, pr source date: {}'
                            .format(len(eligible_addresses), pr_source_date))

                delta_date = timestamp_to_format2(
                    datetime_to_timestamp('{} 00:00:00'.format(self.cache_util._yesterday_cache_date)),
                    timedeltas={'days': 1}, opera=-1)[:10]
                self.cache_util.save_boost_ledger_delta_source(delta_date)
                logger.info('saved boost_ledger_delta_source.json (delta_date={})'.format(delta_date))
                user_points = _ledger_debit_balances(self.cache_util, eligible_addresses, delta_date, logger)
                total_points = sum(user_points.values())
                shares = _compute_shares(user_points)
                logger.info('boost shares count: {}, total points: {}, pr source date: {}'
                            .format(len(shares), total_points, pr_source_date))
                self.cache_util.save_cache_pr_boost(shares)
                logger.info('saved boost_pr.json ({} shares)'.format(len(shares)))
                _carve_out_boost_reward(self.cache_util, logger)
                if check_vote(self.web3eth, logger, self.today_date):
                    return True
            except:
                logger.error(traceback.format_exc())
                time.sleep(5)
            times += 1


def do():
    CalculateBoost().main()


def calculate_boost():
    while True:
        try:
            hour = app_config.BOOST_START_HOUR
            minute = app_config.BOOST_START_MINUTE
            web3eth = Web3Eth(logger)
            latest_proposal = web3eth.get_latest_snapshoot_proposal()
            pagerank_date = get_pagerank_date()
            pagerank_timestamp = datetime_to_timestamp('{} {}:{}:00'.format(pagerank_date,
                                                                            app_config.START_HOUR,
                                                                            app_config.START_MINUTE))
            if latest_proposal[-1] == 1 and latest_proposal[5] > pagerank_timestamp:
                now_timestamp = get_now_timestamp()
                pagerank_datetime = '{} {}:{}:00'.format(pagerank_date, hour, minute)
                target_timestamp = datetime_to_timestamp(pagerank_datetime)
                next_datetime = timestamp_to_format2(target_timestamp, timedeltas={'days': 1}, opera=1)
                next_timestamp = datetime_to_timestamp(next_datetime)
                logger.info('now timestamp: {}, pagerank_datetime: {}, next datetime: {}, next timestamp: {}'
                            .format(now_timestamp, pagerank_datetime, next_datetime, next_timestamp))
                time_interval = next_timestamp - now_timestamp
                if time_interval < app_config.TIME_INTERVAL:
                    logger.info('< time interval, to run.')
                    if time_interval > 0:
                        time.sleep(next_timestamp - now_timestamp)
                        do()
                    else:
                        do()
            else:
                logger.info('the previous proposal failed. to run.')
                do()
            scheduler.add_job(id='calculate_boost2', func=do, trigger='cron', hour=int(hour), minute=int(minute))
            break
        except:
            logger.error(traceback.format_exc())


logger.info('Calculate Boost Job Is Running, pid:{}'.format(os.getpid()))
next_run_time = time_format(timedeltas={"seconds": 20}, opera=1, is_datetime=True)
scheduler.add_job(id='calculate_boost', func=calculate_boost, next_run_time=next_run_time)
