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


def _eligible_rows(rows, prev_pr, logger=None):
    """Only wallets with PR > 0 are eligible for boost; how many points they
    can stack per day is capped separately in _cap_daily_points_to_pr_tier.
    pr.json keys are checksum-cased, lower()'d to match GameHub row
    addresses."""
    eligible = {addr.lower() for addr, share in prev_pr.get('MAINNET', {}).items() if Decimal(str(share)) > 0}
    result = [row for row in rows if row['user'] in eligible]
    if logger:
        logger.info('eligibility filter: {} rows in, {} eligible ({} PR-eligible wallets in prev_pr).'
                    .format(len(rows), len(result), len(eligible)))
    return result


def _pr_tier_cap(share, tier_caps):
    """The max_points cap for the tier whose [min_share, max_share) range
    contains this share, or None if uncovered (left uncapped, not zeroed)."""
    for tier in tier_caps:
        if Decimal(str(tier['min_share'])) <= share < Decimal(str(tier['max_share'])):
            return Decimal(str(tier['max_points']))
    return None


def _cap_daily_points_to_pr_tier(rows, prev_pr, logger=None):
    """Clamps each wallet's raw GameHub points for a SINGLE calendar day (one
    row = one wallet's stake for one dateKey) to its PR tier's max_points
    (BOOST_PR_TIER_CAPS) - a wallet can't stack more points in one day than
    its own tier allows. Applied per row, before _user_points divides/sums
    across the window, so there's no cap on the wallet's total across the
    window - only on how much any single day can contribute to it."""
    tier_caps = app_config.BOOST_PR_TIER_CAPS
    shares = {addr.lower(): Decimal(str(share)) for addr, share in prev_pr.get('MAINNET', {}).items()}
    capped_rows = []
    capped_count = 0
    for row in rows:
        points = Decimal(str(row['points']))
        cap = _pr_tier_cap(shares.get(row['user'], Decimal(0)), tier_caps)
        if cap is not None and cap < points:
            capped_count += 1
            points = cap
        capped_rows.append(dict(row, points=str(points)))
    if logger and capped_count:
        logger.info('pr tier cap: {}/{} daily rows clamped to their tier max_points.'
                    .format(capped_count, len(rows)))
    return capped_rows


def _truncate_decimal(value, places):
    """Truncates (not rounds) a Decimal to `places` decimal places via
    string-slicing - the same technique used across the earnings jobs and
    the core PR engine (network_util.to_precision_decimal). getcontext().prec
    is thread-local, and worker threads don't reliably inherit base_import's
    prec=100 (each APScheduler job can run on its own thread, starting from
    the decimal module's default prec=28) - so the SAME division can carry a
    different number of digits depending purely on which thread/server ran
    it. Truncating every division's result down to a small, fixed number of
    decimal places makes the stored value identical everywhere regardless of
    that ambient precision, instead of persisting however many digits
    happened to be available."""
    s = str(value)
    if 'e-' in s or 'E-' in s:
        s = '%.20f' % value
    parts = s.split('.')
    if len(parts) == 1:
        return Decimal(parts[0])
    return Decimal('{}.{}'.format(parts[0], parts[1][:places]))


def _user_points(rows):
    """Each wallet's total points across the window, each row's points
    (already clamped per-day by _cap_daily_points_to_pr_tier) divided by
    BOOST_LOOKBACK_DAYS before summing so the multi-day total stays on the
    same scale as a single day's pr_reward pool (compared against in
    _carve_out_boost_reward). Doesn't affect shares, only the absolute
    total_points figure. Negative daily totals clamp to 0. Each day's
    division is truncated to EARNINGS_ACCURACY decimal places before summing
    (see _truncate_decimal) so the per-wallet total - and therefore
    total_points, since summing already-truncated exact values can't
    introduce new precision-dependent digits - comes out identical on every
    node. The sum itself is uncapped - a wallet can accumulate as many capped
    days as it has, with no ceiling on the window total."""
    lookback_days = Decimal(app_config.BOOST_LOOKBACK_DAYS)
    user_points = {}
    for row in rows:
        addr = row['user'].lower()
        daily = _truncate_decimal(Decimal(str(row['points'])) / lookback_days, app_config.EARNINGS_ACCURACY)
        user_points[addr] = user_points.get(addr, 0) + daily
    return {addr: max(points, 0) for addr, points in user_points.items()}


def _compute_shares(user_points):
    """Each wallet's share (0-1 fraction) of the window's total points -
    same convention as pr.json, mirrored here for boost_pr.json. Truncated
    to EARNINGS_ACCURACY decimal places for the same cross-node consistency
    reason as _user_points - this division is the other spot (besides the
    per-day one above) that can produce a repeating decimal."""
    total_points = sum(user_points.values())
    if total_points <= 0:
        return {}
    return {addr: str(_truncate_decimal(points / total_points, app_config.EARNINGS_ACCURACY))
            for addr, points in user_points.items() if points > 0}


def compute_wallet_boost_reward(share, pool):
    """A wallet's absolute reward for its share of the boost_reward pool,
    truncated (not rounded) to EARNINGS_ACCURACY decimal places - shared by
    _rebuild_boost_reward below and reward_boost_pr_job's normal first-time
    computation, so both ever compute a payout the same way."""
    return _truncate_decimal(pool * share, app_config.EARNINGS_ACCURACY)


def _rebuild_boost_reward(cache_util, logger, pool):
    """Rebuilds boost_reward.json against the given pool immediately,
    synchronously - called from _carve_out_boost_reward when it discards a
    stale carve. Doesn't rely on reward_boost_pr_job's own daily cycle still
    being around to notice the file is gone and regenerate it (it may have
    already voted and exited for today), so the payout list is never left
    stale OR missing."""
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


def _carve_out_boost_reward(cache_util, logger, total_points):
    """Carves boost_reward out of today's pr_reward (rather than minting it
    separately), capped to BOOST_REWARD_MAX_PR_SHARE of pr_reward so a spike
    in boost demand can't eat more than that share. Safe to call from both
    calculate_boost_job and reward_boost_pr_job (as a safety net) - a repeat
    call with the SAME total_points is a no-op. A repeat call with a
    DIFFERENT total_points (boost_pr.json got recomputed since the last
    carve, e.g. after a boost_memory.json reset) discards the stale carve,
    redoes it against the new total, and immediately rebuilds
    boost_reward.json to match (rather than merely deleting it and hoping
    reward_boost_pr_job's own cycle is still running to regenerate it) - the
    same delete-then-recalculate pattern data_job uses elsewhere, made
    airtight rather than dependent on another job's timing. Restoring
    pr_reward's pre-carve value is exact (Decimal +/- is lossless), so
    repeated carve/discard cycles can't drift."""
    day_amount = cache_util.get_today_day_amount()
    prior_total_points = day_amount.get('boost_reward_total_points')
    if prior_total_points is not None and prior_total_points == total_points:
        return
    discarding_stale_reward = prior_total_points is not None
    if discarding_stale_reward:
        logger.info('boost total_points changed ({} -> {}) since the last carve - discarding the stale carve, '
                    'recalculating.'.format(prior_total_points, total_points))
        day_amount['pr_reward'] = day_amount.get('pr_reward', 0) + day_amount.get('boost_reward', 0)
        del day_amount['boost_reward']
        del day_amount['boost_reward_total_points']
    pr_reward = day_amount.get('pr_reward', 0)
    max_boost_reward = pr_reward * Decimal(str(app_config.BOOST_REWARD_MAX_PR_SHARE))
    boost_reward = min(total_points, max_boost_reward)
    if total_points > max_boost_reward:
        logger.info('boost demand {} exceeds {:.0%} of pr_reward ({}) - capping boost_reward to {}.'
                    .format(total_points, app_config.BOOST_REWARD_MAX_PR_SHARE, pr_reward, boost_reward))
    day_amount['pr_reward'] = pr_reward - boost_reward
    day_amount['boost_reward'] = boost_reward
    day_amount['boost_reward_total_points'] = str(total_points)
    # save_boost_day_amount (not save_cache_day_amount): while BOOST_DATA_DIR
    # is on, this carve must land in the isolated <date>-boost folder, not
    # mutate the live day_amount.json the main PR pipeline depends on. Once
    # that flag is off, save_boost_day_amount resolves to the same file
    # save_cache_day_amount would have written anyway - config-only switch.
    cache_util.save_boost_day_amount(day_amount)
    # luca_amount.json's prReward is what day_amount.json's pr_reward was
    # originally derived from (coin_util.day_amount) - carry the same
    # carved-down value so the two files don't silently disagree. Always
    # recomputed from the pristine main-folder luca_amount (not restored
    # from a prior carve), same reasoning as day_amount's pr_reward baseline
    # above: that source is never itself mutated while BOOST_DATA_DIR is
    # True, so there's nothing to reverse.
    luca_amount = cache_util.get_today_luca_amount()
    luca_amount['prReward'] = str(Decimal(str(luca_amount.get('prReward', 0))) - boost_reward)
    # boostReward mirrors day_amount's boost_reward key, camelCased to match
    # luca_amount.json's own naming convention (pledgeReward, nodeReward,
    # etc.) - without it, prReward being lower than the source API returned
    # would have no explanation sitting in this file alone.
    luca_amount['boostReward'] = str(boost_reward)
    cache_util.save_boost_luca_amount(luca_amount)
    if discarding_stale_reward:
        _rebuild_boost_reward(cache_util, logger, boost_reward)


class CalculateBoost():
    def __init__(self):
        # Boost runs on its own cutoff (BOOST_START_HOUR/MINUTE), not the
        # main PR job's (START_HOUR/MINUTE).
        self.today_date = get_pagerank_date(app_config.BOOST_START_HOUR, app_config.BOOST_START_MINUTE)
        self.web3eth = Web3Eth(logger)
        self.cache_util = CacheUtil(hour=app_config.BOOST_START_HOUR, minute=app_config.BOOST_START_MINUTE)

    def wait_memory(self):
        """Waits up to VOTE_EPOCH minutes for boost_memory_job to signal a
        completed fetch pass for TODAY's boost date (memory['ready_date'] ==
        self.today_date), not merely for boost_memory.json to exist - it's a
        single persistent file (see CacheUtil.get_boost_memory), so it's
        already there from a previous day and its mere existence says
        nothing about whether today's window has been fetched yet."""
        start_timestamp = get_now_timestamp()
        while True:
            memory = self.cache_util.get_boost_memory()
            if memory.get('ready_date') == self.today_date:
                time.sleep(1)
                return True
            if get_now_timestamp() - start_timestamp > app_config.VOTE_EPOCH * 60:
                return False
            time.sleep(1)

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
                # Recompute every pass (not just once) rather than locking
                # in boost_pr.json off whatever dateKeys happened to be
                # finalized on the FIRST pass. A dateKey can finalize in the
                # same few-second window a node happens to poll - freezing
                # after one computation risks permanently missing it, since
                # nothing revisits boost_pr.json once it's written (and
                # data_job's delete_datas() correctly no longer wipes it to
                # force a revisit either). _carve_out_boost_reward already
                # reconciles day_amount.json/boost_reward.json whenever
                # total_points changes between passes, so recomputing here
                # is safe - it converges to the true finalized set over the
                # (typically many-hour) window before check_vote succeeds,
                # instead of gambling on the first pass being complete.
                if not self.wait_memory():
                    logger.info('boost memory not ready for {} within wait window - '
                                'using last known good state.'.format(self.today_date))
                memory = self.cache_util.get_boost_memory()
                prev_pr, pr_source_date = _previous_pr(logger)
                self.cache_util.save_boost_pr_source(prev_pr, pr_source_date)
                rows = _eligible_rows(_flatten_rows(memory), prev_pr, logger)
                rows = _cap_daily_points_to_pr_tier(rows, prev_pr, logger)
                user_points = _user_points(rows)
                total_points = sum(user_points.values())
                shares = _compute_shares(user_points)
                logger.info('boost shares count: {}, total points: {}, pr source date: {}'
                            .format(len(shares), total_points, pr_source_date))
                # Save shares now rather than holding them behind the
                # carve-out, which can't run until data_job writes
                # day_amount.json ~3 hours later.
                self.cache_util.save_cache_pr_boost(shares, total_points)
                _carve_out_boost_reward(self.cache_util, logger, total_points)
                if check_vote(self.web3eth, logger, self.today_date):
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
            trigger_hour = hour
            trigger_minute = minute
            web3eth = Web3Eth(logger)
            latest_proposal = web3eth.get_latest_snapshoot_proposal()
            pagerank_date = get_pagerank_date()
            pagerank_timestamp = datetime_to_timestamp('{} {}:{}:00'.format(pagerank_date,
                                                                            app_config.START_HOUR,
                                                                            app_config.START_MINUTE))
            if latest_proposal[-1] == 1 and latest_proposal[5] > pagerank_timestamp:
                now_timestamp = get_now_timestamp()
                pagerank_datetime = '{} {}:{}:00'.format(pagerank_date, trigger_hour, trigger_minute)
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
            scheduler.add_job(id='calculate_boost2', func=do, trigger='cron', hour=int(trigger_hour), minute=int(trigger_minute))
            break
        except:
            logger.error(traceback.format_exc())


logger.info('Calculate Boost Job Is Running, pid:{}'.format(os.getpid()))
next_run_time = time_format(timedeltas={"seconds": 20}, opera=1, is_datetime=True)
scheduler.add_job(id='calculate_boost', func=calculate_boost, next_run_time=next_run_time)
