import time
import random

_MAX_ATTEMPTS = 30
_POLL_INTERVAL_SECONDS = 10


def get_yesterday_file_id(web3eth, timestamp):
    """Polls get_latest_success_snapshoot_proposal() until it reports a
    proposal at or after `timestamp`, then returns that proposal's file id.

    Gives up after _MAX_ATTEMPTS polls (a broken proposal chain shouldn't
    spin every caller forever) by raising TimeoutError rather than
    returning the last-seen (and by definition, still-stale) proposal's
    file id - a stale id would be indistinguishable from a real match to
    every one of this function's 5 callers, each of which would then
    silently download/process the wrong day's data under today's filename.
    Every caller already wraps its own call chain in a broad try/except
    that logs and retries on the next cron cycle (the same pattern used
    throughout this codebase for "not ready yet, try again later"), so
    raising here surfaces the stuck state the same way instead of
    fabricating a plausible-looking wrong answer.

    Both failure modes - "proposal exists but isn't fresh yet" and "RPC
    call raised" - count toward the same bound and sleep between polls, so
    a persistently-erroring RPC also eventually gives up instead of
    spinning forever, and the bound spans a meaningful amount of wall-clock
    time instead of bursting through in under a second."""
    attempts = 0
    while True:
        try:
            res = web3eth.get_latest_success_snapshoot_proposal()
            if res[-2] >= timestamp:
                return res[3]
        except Exception:
            pass
        attempts += 1
        if attempts > _MAX_ATTEMPTS:
            raise TimeoutError(
                'get_yesterday_file_id: no proposal at or after {} after {} attempts.'.format(
                    timestamp, _MAX_ATTEMPTS))
        time.sleep(_POLL_INTERVAL_SECONDS + random.uniform(0, _POLL_INTERVAL_SECONDS))
