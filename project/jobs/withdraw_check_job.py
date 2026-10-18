from project.jobs.base_import import *
from project.utils.withdraw_event_util import advance_check_cursor, approved_end_block, check_cursor, \
    latest_day_end_block, prefetch_cursor, reconcile_withdraw_events

# how often the job runs, in minutes - every 10 while it catches up; to be tuned
CHECK_INTERVAL_MINUTES = 10
# Runs are lined up this many minutes after the day boundary (OTHER_HOUR:
# OTHER_MINUTE), so one run covers the whole closed day - the prefetch cursor
# is past the boundary by then - before the data job starts at START_HOUR.
CHECK_OFFSET_MINUTES = 5
# Partial getLogs answers only happen near the chain tip (an RPC whose log
# index lags its block number), so the check stays this far behind the
# prefetch cursor (~90s at ~0.45s per block) - one read of a range is then
# enough.
SAFETY_BLOCKS = 200
# caps one run (~31h of blocks) - a full pending day fits in one run; anything
# beyond, after long downtime, is picked up next run
MAX_BLOCKS_PER_RUN = 250000


class WithdrawCheck():
    """Re-reads WithdrawToken events from the chain and records any the
    2-minute prefetch job missed, so a node heals itself without manual work.

    Moves forward from its own cursor (withdraw_check_block.json) and never
    re-reads a range it has covered or a day already approved (final), so each
    block of the day still to be approved is read once.
    """

    def __init__(self):
        self.p_event_data_dir = os.path.join(data_dir, 'prefetching_events')

    def main(self):
        if not os.path.exists(self.p_event_data_dir):
            logger.info('no prefetching_events dir yet.')
            return True
        prefetched = prefetch_cursor(self.p_event_data_dir)
        if not prefetched:
            logger.info('prefetch job has no cursor yet.')
            return True
        safe_end = prefetched - SAFETY_BLOCKS
        web3eth = Web3Eth(logger)
        # never before the last approved day's end - those days are final
        approved = approved_end_block(web3eth, data_dir, self.p_event_data_dir)
        floors = [b for b in (check_cursor(self.p_event_data_dir), approved) if b is not None]
        if not floors:
            # fresh node: start where the open day starts
            floors = [b for b in (latest_day_end_block(self.p_event_data_dir),) if b is not None]
        if not floors:
            logger.info('no block to start checking from yet.')
            return True
        start = max(floors)
        if safe_end <= start:
            logger.info('nothing new to check (cursor {}, safe end {}).'.format(start, safe_end))
            return True
        end = min(safe_end, start + MAX_BLOCKS_PER_RUN)
        logger.info('checking blocks {}-{} (approved day ends at {}).'.format(start + 1, end, approved))
        result = reconcile_withdraw_events(web3eth, self.p_event_data_dir, start, end, logger)
        if result['skipped']:
            # leave the cursor so the whole range is read again next run
            logger.info('{} event(s) skipped, not advancing past block {}.'.format(result['skipped'], start))
            return True
        advance_check_cursor(self.p_event_data_dir, end)
        if result['healed']:
            process_logger.info('withdraw check: recorded {} missed withdrawal(s) in blocks {}-{}.'.format(
                len(result['healed']), start + 1, end))
        return True


logger = logging.getLogger('withdraw_check')


def do():
    try:
        WithdrawCheck().main()
        return True
    except:
        logger.error(traceback.format_exc())
        return False


logger.info('withdraw check job started, pid:{}'.format(os.getpid()))
# one run at a time (the scheduler default allows 3) - a slow run is never doubled up
first_minute = (int(app_config.OTHER_MINUTE) + CHECK_OFFSET_MINUTES) % CHECK_INTERVAL_MINUTES
scheduler.add_job(id='withdraw_check', func=do, trigger='cron',
                  minute='{}/{}'.format(first_minute, CHECK_INTERVAL_MINUTES), max_instances=1)
