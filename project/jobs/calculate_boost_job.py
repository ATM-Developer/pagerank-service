from project.jobs.base_import import *

logger = logging.getLogger('calculate_boost')


def _flatten_rows(memory):
    rows = []
    for instance_history in (memory.get('history') or {}).values():
        for date_key_rows in instance_history.values():
            rows.extend(date_key_rows)
    return rows


_FALLBACK_LOOKBACK_DAYS = 30


def _most_recent_json(file_name, logger, start_days_back=1):
    """Walks backward from start_days_back for the first <file_name> found
    under data_dir/<date>/, so a missing/late file falls back to the most
    recent one instead of blocking or crashing."""
    for days_back in range(start_days_back, _FALLBACK_LOOKBACK_DAYS + 1):
        date = time_format(timedeltas={'days': days_back}, opera=-1)[:10]
        file_path = os.path.join(data_dir, date, file_name)
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                logger.info('boost job falling back to {} from {}'.format(file_name, date))
                return json.load(f), date
    logger.info('no {} found in the last {} days'.format(file_name, _FALLBACK_LOOKBACK_DAYS))
    return {}, None


def _previous_pr(logger):
    """Falls back to the most recent pr.json if today's isn't ready yet - a
    stale eligibility snapshot beats the boost pipeline stalling. Returns
    (pr_data, source_date) for traceability."""
    return _most_recent_json(CacheUtil._PR_FILE_NAME, logger)


def _previous_boost_memory(logger):
    """Falls back to the most recent boost_memory.json if today's isn't
    ready within wait_memory()'s bound."""
    memory, _source_date = _most_recent_json(CacheUtil._BOOST_MEMORY_FILE_NAME, logger)
    return memory


def _eligible_rows(rows, prev_pr):
    """Only wallets with PR > 0 are eligible for boost; how many points they
    can claim is capped separately in _cap_points_to_pr_tier. pr.json keys
    are checksum-cased, lower()'d to match GameHub row addresses."""
    eligible = {addr.lower() for addr, share in prev_pr.get('MAINNET', {}).items() if Decimal(str(share)) > 0}
    return [row for row in rows if row['user'] in eligible]


def _pr_tier_cap(share, tier_caps):
    """The max_points cap for the tier whose [min_share, max_share) range
    contains this share, or None if uncovered (left uncapped, not zeroed)."""
    for tier in tier_caps:
        if Decimal(str(tier['min_share'])) <= share < Decimal(str(tier['max_share'])):
            return Decimal(str(tier['max_points']))
    return None


def _cap_points_to_pr_tier(user_points, prev_pr):
    """Clamps each wallet's points to its PR tier's max_points
    (BOOST_PR_TIER_CAPS) - a wallet can't out-earn its own tier by racking up
    GameHub points beyond the cap."""
    tier_caps = app_config.BOOST_PR_TIER_CAPS
    shares = {addr.lower(): Decimal(str(share)) for addr, share in prev_pr.get('MAINNET', {}).items()}
    capped = {}
    for addr, points in user_points.items():
        cap = _pr_tier_cap(shares.get(addr, Decimal(0)), tier_caps)
        capped[addr] = min(points, cap) if cap is not None else points
    return capped


def _user_points(rows):
    """Each wallet's total points across the window, each row's points
    divided by BOOST_LOOKBACK_DAYS before summing so the multi-day total
    stays on the same scale as a single day's pr_reward pool (compared
    against in _carve_out_boost_reward). Doesn't affect shares, only the
    absolute total_points figure. Negative daily totals clamp to 0."""
    lookback_days = Decimal(app_config.BOOST_LOOKBACK_DAYS)
    user_points = {}
    for row in rows:
        addr = row['user'].lower()
        user_points[addr] = user_points.get(addr, 0) + Decimal(str(row['points'])) / lookback_days
    return {addr: max(points, 0) for addr, points in user_points.items()}


def _compute_shares(user_points):
    """Each wallet's share (0-1 fraction) of the window's total points -
    same convention as pr.json, mirrored here for boost_pr.json."""
    total_points = sum(user_points.values())
    if total_points <= 0:
        return {}
    return {addr: str(points / total_points) for addr, points in user_points.items() if points > 0}


def _carve_out_boost_reward(cache_util, logger, total_points):
    """Carves boost_reward out of today's pr_reward (rather than minting it
    separately), capped to BOOST_REWARD_MAX_PR_SHARE of pr_reward so a spike
    in boost demand can't eat more than that share. Idempotent via the
    'boost_reward' key check, so it's safe to call from both
    calculate_boost_job and reward_boost_pr_job (as a safety net)."""
    day_amount = cache_util.get_today_day_amount()
    if 'boost_reward' in day_amount:
        return
    pr_reward = day_amount.get('pr_reward', 0)
    max_boost_reward = pr_reward * Decimal(str(app_config.BOOST_REWARD_MAX_PR_SHARE))
    boost_reward = min(total_points, max_boost_reward)
    if total_points > max_boost_reward:
        logger.info('boost demand {} exceeds {:.0%} of pr_reward ({}) - capping boost_reward to {}.'
                    .format(total_points, app_config.BOOST_REWARD_MAX_PR_SHARE, pr_reward, boost_reward))
    day_amount['pr_reward'] = pr_reward - boost_reward
    day_amount['boost_reward'] = boost_reward
    cache_util.save_cache_day_amount(day_amount)


class CalculateBoost():
    def __init__(self):
        self.data_file_path = data_dir
        # Boost runs on its own cutoff (BOOST_START_HOUR/MINUTE), not the
        # main PR job's (START_HOUR/MINUTE).
        self.today_date = get_pagerank_date(app_config.BOOST_START_HOUR, app_config.BOOST_START_MINUTE)
        self.today_file_path = os.path.join(self.data_file_path, self.today_date)
        self.web3eth = Web3Eth(logger)
        self.cache_util = CacheUtil(hour=app_config.BOOST_START_HOUR, minute=app_config.BOOST_START_MINUTE)

    def wait_memory(self):
        """Waits up to VOTE_EPOCH minutes for today's boost_memory.json,
        then gives up so the caller can fall back to an older day's memory."""
        memory_path = os.path.join(self.today_file_path, CacheUtil._BOOST_MEMORY_FILE_NAME)
        start_timestamp = get_now_timestamp()
        while True:
            if os.path.exists(memory_path):
                time.sleep(1)
                return True
            if get_now_timestamp() - start_timestamp > app_config.VOTE_EPOCH * 60:
                return False
            time.sleep(1)

    def main(self):
        flag_file_path = os.path.join(self.today_file_path, CacheUtil._BOOST_PR_FILE_NAME)
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
                if not os.path.exists(flag_file_path):
                    logger.info('calculate boost shares.')
                    if self.wait_memory():
                        memory = self.cache_util.get_today_boost_memory()
                    else:
                        memory = _previous_boost_memory(logger)
                    prev_pr, pr_source_date = _previous_pr(logger)
                    self.cache_util.save_boost_pr_source(prev_pr, pr_source_date)
                    rows = _eligible_rows(_flatten_rows(memory), prev_pr)
                    user_points = _user_points(rows)
                    user_points = _cap_points_to_pr_tier(user_points, prev_pr)
                    total_points = sum(user_points.values())
                    shares = _compute_shares(user_points)
                    logger.info('boost shares count: {}, total points: {}, pr source date: {}'
                                .format(len(shares), total_points, pr_source_date))
                    # Save shares now rather than holding them behind the
                    # carve-out, which can't run until data_job writes
                    # day_amount.json ~3 hours later.
                    self.cache_util.save_cache_pr_boost(shares, total_points)
                else:
                    total_points = Decimal(self.cache_util.get_today_pr_boost()['total_points'])
                _carve_out_boost_reward(self.cache_util, logger, total_points)
                if check_vote(self.web3eth, logger, self.today_date, flag_file_path):
                    return True
            except:
                logger.error(traceback.format_exc())
                # Back off like the not-senator/executer branch above, so an
                # outage doesn't turn into a tight retry loop.
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
