from project.jobs.base_import import *
from project.utils.game_hub_util import GameHubReader
from project.jobs.calculate_boost_job import _previous_pr, _eligible_rows, _check_pr_tier_range, _truncate_decimal, \
    _cap_backfill_rows

logger = logging.getLogger('boost_data')

_BOOST_LEDGER_SCHEMA_VERSION = 1


def _maybe_migrate_to_ledger_schema(cache_util, memory, logger):
    if memory.get('ledger_schema_version') == _BOOST_LEDGER_SCHEMA_VERSION:
        return memory
    logger.info('boost_memory.json predates the permanent-ledger schema (or is missing it) - resetting its '
               'cursor for a one-time full rescan from BOOST_START_DATE.')
    memory = {'ledger_schema_version': _BOOST_LEDGER_SCHEMA_VERSION}
    cache_util.save_boost_memory(memory)
    return memory


def reset_todays_boost_credit_if_unfolded(cache_util, logger, today_date=None):
    """Recovery primitive for a boost-data-caused vote mismatch: rolls back
    only TODAY's per-instance credit cursor in boost_memory.json, so
    _credit_active_instances() re-derives today's boost_delta.json fresh
    from GameHub on its next pass. Deliberately narrow and pre-fold-only:

    - Refuses outright if today's boost_ledger_fold_cursor.json already
      shows last_folded_date >= today - data_job.py's
      _update_boost_ledger_for_today() folds via point_balance = old_balance
      + change (additive, not idempotent), so re-crediting a date that's
      already been folded would double-count it on the next fold. Once
      that's happened, this function can't safely undo it - it's a no-op.
    - Only rolls cursor[key] back by one dateKey, for instances whose
      finalized_through[key]['calendar_date'] is today - every earlier
      day's cursor/delta/point_balance is left untouched. This mirrors the
      same 'cursor[key] = date_key - 1' self-heal _credit_active_instances()
      already does for a locally-inconsistent entry, just targeted
      deliberately at today instead of triggered by a local consistency
      check.
    - finalized_through[key] is left as-is; the next successful credit pass
      overwrites it along with the delta file, so there's nothing to clean
      up there.

    Caller's responsibility: decide *when* to call this (e.g. after
    comparison_all_data() reports a boost-related mismatch and today's fold
    hasn't run yet) - this function only enforces that it's safe to do so,
    not why. Returns True if a reset happened, False if it was a no-op."""
    if today_date is None:
        today_date = get_pagerank_date(app_config.BOOST_START_HOUR, app_config.BOOST_START_MINUTE)

    fold_cursor = cache_util.get_boost_ledger_fold_cursor()
    if fold_cursor and fold_cursor.get('last_folded_date', '') >= today_date:
        logger.warning('reset_todays_boost_credit_if_unfolded: refusing - boost_ledger_fold_cursor.json already '
                       'folded through {} (>= today {}). Resetting now would double-count on the next fold. '
                       'No-op.'.format(fold_cursor.get('last_folded_date'), today_date))
        return False

    memory = cache_util.get_boost_memory()
    cursor = dict(memory.get('cursor') or {})
    finalized_through = dict(memory.get('finalized_through') or {})
    rolled_back = [key for key, entry in finalized_through.items()
                   if entry.get('calendar_date') == today_date and key in cursor]
    if not rolled_back:
        logger.info('reset_todays_boost_credit_if_unfolded: nothing credited for {} yet - nothing to reset.'
                    .format(today_date))
        return False

    for key in rolled_back:
        cursor[key] = cursor[key] - 1
    memory['cursor'] = cursor
    memory['updated_at'] = get_now_timestamp()
    cache_util.save_boost_memory(memory)
    logger.warning('reset_todays_boost_credit_if_unfolded: rolled back {} instance(s) cursor by one dateKey for '
                   '{} - {}. Next credit pass will re-derive today fresh from GameHub.'
                   .format(len(rolled_back), today_date, rolled_back))
    return True


def _credit_date_rows(cache_util, date_rows, prev_pr, calendar_date, instance_key, logger, today_date,
                       filter_by_pr=True):
    if filter_by_pr:
        # Backfilled (non-today) dates skip PR eligibility entirely: this
        # node doesn't have that day's historical pr.json, so gating on
        # today's pr.json would answer "eligible right now", not "eligible
        # back then" - and since a (calendar_date, instance) pair is only
        # ever credited once, two nodes backfilling the same dateKey at
        # different real times could permanently disagree on the same
        # wallet. Only the tier cap (a fixed rule, no live PR involved)
        # applies to backfill; today's own crediting still gates on live PR.
        if calendar_date == today_date:
            date_rows = _eligible_rows(date_rows, prev_pr, logger)
            date_rows = _check_pr_tier_range(date_rows, prev_pr, logger)
        else:
            date_rows = _cap_backfill_rows(date_rows, logger)
    new_delta = {}
    for row in date_rows:
        address = row['user']
        points = Decimal(str(row['points']))
        new_delta[address] = str(_truncate_decimal(
            Decimal(new_delta.get(address, '0')) + points, app_config.EARNINGS_ACCURACY))
    chain_total = sum(Decimal(v) for v in new_delta.values())
    logger.info('boost credit from chain: date {}, instance {}, {} row(s), {} wallet(s), total {} points.'
                .format(calendar_date, instance_key, len(date_rows), len(new_delta), chain_total))
    all_deltas = cache_util.get_boost_ledger_delta(calendar_date)
    all_deltas[instance_key] = new_delta
    cache_util.save_boost_ledger_delta(calendar_date, all_deltas)


class BoostMemory():
    def __init__(self):
        self.data_file_path = data_dir
        self.today_date = get_pagerank_date(app_config.BOOST_START_HOUR, app_config.BOOST_START_MINUTE)
        self.today_file_path = os.path.join(self.data_file_path, self.today_date)
        self.web3eth = Web3Eth(logger)
        self.cache_util = CacheUtil(hour=app_config.BOOST_START_HOUR, minute=app_config.BOOST_START_MINUTE)

    def _credit_active_instances(self):
        reader = GameHubReader(logger)
        memory = self.cache_util.get_boost_memory()
        memory = _maybe_migrate_to_ledger_schema(self.cache_util, memory, logger)
        cursor = dict(memory.get('cursor') or {})
        finalized_through = dict(memory.get('finalized_through') or {})
        for key, date_key in list(cursor.items()):
            calendar_date = (finalized_through.get(key) or {}).get('calendar_date')
            if calendar_date is None:
                logger.warning('cursor for {} claims dateKey {} but has no finalized_through record '
                               '(old-format data?) - rolling back to re-derive and backfill it.'
                               .format(key, date_key))
                cursor[key] = date_key - 1
                continue
            if key not in self.cache_util.get_boost_ledger_delta(calendar_date):
                logger.warning('cursor for {} claims dateKey {} ({}) is credited, but no matching '
                               'boost_ledger_delta record exists on disk - rolling back to re-derive it.'
                               .format(key, date_key, calendar_date))
                cursor[key] = date_key - 1
        prev_pr, pr_source_date = _previous_pr(logger)
        if pr_source_date is None:
            logger.info('no pr.json available yet - skipping this credit pass instead of crediting '
                        'against an empty eligibility set.')
            return False
        operators = reader.get_active_operators()
        logger.info('boost memory: {} active operators, pr source date: {}'.format(len(operators), pr_source_date))
        credited_rows = 0
        for operator in operators:
            try:
                instance_address = reader.get_instance(operator)
                if not instance_address or int(instance_address, 16) == 0:
                    logger.info('operator {} has no instance deployed - skipping.'.format(operator))
                    continue
                key = instance_address.lower()

                def _on_date_done(calendar_date, date_key, date_rows, voucher_rows, key=key):
                    if key not in cursor:
                        expected_date_key = date_key
                    else:
                        expected_date_key = cursor[key] + 1
                    if date_key != expected_date_key:
                        logger.info('dateKey {} for {} is ahead of an unfinalized gap (cursor at {}) - '
                                    'deferring to a later pass.'.format(date_key, key, cursor.get(key)))
                        return
                    _credit_date_rows(self.cache_util, date_rows, prev_pr, calendar_date, key, logger,
                                      self.today_date)
                    _credit_date_rows(self.cache_util, voucher_rows, prev_pr, calendar_date, '{}:voucher'.format(key),
                                      logger, self.today_date, filter_by_pr=False)
                    cursor[key] = date_key
                    memory['cursor'] = cursor
                    finalized_through[key] = {'date_key': date_key, 'calendar_date': calendar_date}
                    memory['finalized_through'] = finalized_through
                    memory['updated_at'] = get_now_timestamp()
                    self.cache_util.save_boost_memory(memory)

                new_rows, _earliest_calendar_date, _last_finalized_date_key = reader.fetch_instance_day(
                    instance_address, cursor.get(key), on_date_done=_on_date_done, known_calendar_dates=None)
                credited_rows += len(new_rows)
            except Exception:
                logger.error('operator {} fetch/credit failed: {}'.format(operator, traceback.format_exc()))
        memory = self.cache_util.get_boost_memory()
        memory['ready_date'] = self.today_date
        memory['updated_at'] = get_now_timestamp()
        self.cache_util.save_boost_memory(memory)
        logger.info('boost memory: credited {} new row(s) across {} operator(s).'.format(credited_rows, len(operators)))
        return True

    def main(self):
        times = 1
        while True:
            try:
                start_timestamp = get_now_timestamp()
                logger.info('boost memory times: {}, time: {}'.format(times, start_timestamp))
                node_result = self.web3eth.is_senators_or_executer()
                logger.info('self address is : {}'.format(node_result))
                if not node_result:
                    if self.web3eth.check_vote() == 1:
                        return True
                    else:
                        time.sleep(5)
                        continue
                logger.info('credit boost ledger from GameHub.')
                fetch_start_timestamp = get_now_timestamp()
                credited = self._credit_active_instances()
                logger.info('boost memory credit pass took {:.2f}s'.format(get_now_timestamp() - fetch_start_timestamp))
                if not credited:
                    time.sleep(5)
                    continue
                if check_vote(self.web3eth, logger, self.today_date):
                    return True
            except:
                logger.error(traceback.format_exc())
                time.sleep(5)
            times += 1


def do():
    BoostMemory().main()


def boost_memory():
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
            scheduler.add_job(id='boost_memory2', func=do, trigger='cron', hour=int(hour), minute=int(minute))
            break
        except:
            logger.error(traceback.format_exc())


logger.info('Boost Memory Job Is Running, pid:{}'.format(os.getpid()))
next_run_time = time_format(timedeltas={"seconds": 20}, opera=1, is_datetime=True)
scheduler.add_job(id='boost_memory', func=boost_memory, next_run_time=next_run_time)

# Every 2h instead of every 30min (48/day -> 10/day), and paused 18:00-23:00
# UTC entirely - that window is exactly boost_start_hour(18:15)/other_hour
# (21:00)/start_hour(21:15), i.e. the actual daily computation already
# running its own dedicated pass (boost_memory2 above, fired once at
# boost_start_hour). Polling again in the middle of that window doesn't
# get today's data any fresher - by 18:15 whatever this background check
# has already collected is what the day's pass uses - it just spends more
# RPC/GameHub calls competing with the real pass while it's running. Runs
# at 23,1,3,...,17 (10 times) covering the rest of the day; resumes at 23:00
# with a fresh cycle. For an on-demand full pass outside this cadence (e.g.
# recovery/backfill), call do() / BoostMemory().main() directly rather than
# waiting for the next tick.
scheduler.add_job(id='boost_memory_check', func=do, trigger='cron',
                  hour='23,1,3,5,7,9,11,13,15,17', minute='0')
