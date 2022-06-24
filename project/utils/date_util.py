import pytz
import datetime
from dateutil import tz
from project.extensions import app_config

tz_utc = tz.gettz('utc')


def get_pagerank_date(hour=None, minute=None):
    tz = pytz.timezone('UTC')
    pagerank_time = datetime.datetime.now(tz)
    if hour is None:
        hour = app_config.START_HOUR
    if minute is None:
        minute = app_config.START_MINUTE
    if pagerank_time >= datetime.datetime(pagerank_time.year, pagerank_time.month, pagerank_time.day, int(hour),
                                          int(minute), tzinfo=tz):
        pass
    else:
        pagerank_time = pagerank_time + datetime.timedelta(days=-1)
    pagerank_date = pagerank_time.strftime('%Y-%m-%d')
    return pagerank_date


def get_previous_pagerank_date(hour=None, minute=None):
    tz = pytz.timezone('UTC')
    now_time = datetime.datetime.now(tz) + datetime.timedelta(days=-1)
    if hour is None:
        hour = app_config.START_HOUR
    if minute is None:
        minute = app_config.START_MINUTE
    if now_time >= datetime.datetime(now_time.year, now_time.month, now_time.day, hour, minute, tzinfo=tz):
        previous_pagerank_date = now_time.strftime('%Y-%m-%d')
    else:
        previous_pagerank_date = (now_time + datetime.timedelta(days=-1)).strftime('%Y-%m-%d')
    return previous_pagerank_date


def time_format(dtime=None, timedeltas={}, opera=None, is_datetime=False):
    if dtime is None:
        dtime = datetime.datetime.now(tz_utc)
    if 'days' in timedeltas:
        if opera == -1:
            dtime = dtime - datetime.timedelta(days=timedeltas['days'])
        elif opera == 1:
            dtime = dtime + datetime.timedelta(days=timedeltas['days'])
    if 'hours' in timedeltas:
        if opera == -1:
            dtime = dtime - datetime.timedelta(hours=timedeltas['hours'])
        elif opera == 1:
            dtime = dtime + datetime.timedelta(hours=timedeltas['hours'])
    if 'minutes' in timedeltas:
        if opera == -1:
            dtime = dtime - datetime.timedelta(minutes=timedeltas['minutes'])
        elif opera == 1:
            dtime = dtime + datetime.timedelta(minutes=timedeltas['minutes'])
    if 'seconds' in timedeltas:
        if opera == -1:
            dtime = dtime - datetime.timedelta(seconds=timedeltas['seconds'])
        elif opera == 1:
            dtime = dtime + datetime.timedelta(seconds=timedeltas['seconds'])
    if is_datetime:
        return dtime
    else:
        return dtime.strftime("%Y-%m-%d %H:%M:%S")


def get_now_timestamp():
    return datetime.datetime.now(tz_utc).timestamp()


def timestamp_to_format(timestamp):
    timestamp = timestamp[:-6] + "." + timestamp[-6:]
    timestamp = float(timestamp)
    return timestamp_to_format2(timestamp)


def timestamp_to_format2(timestamp, timedeltas={}, opera=None, is_datetime=False):
    return time_format(datetime.datetime.fromtimestamp(timestamp).astimezone(tz_utc), timedeltas, opera, is_datetime)


def datetime_to_timestamp(sdatetime):
    if isinstance(sdatetime, str):
        sdatetime = datetime.datetime.strptime(sdatetime, '%Y-%m-%d %H:%M:%S')
    year = sdatetime.year
    month = sdatetime.month
    day = sdatetime.day
    hour = sdatetime.hour
    minute = sdatetime.minute
    second = sdatetime.second
    return datetime.datetime(year, month, day, hour, minute, second, tzinfo=tz_utc).timestamp()


def get_dates_list(start_date, end_date):
    date_list = [start_date]
    while True:
        year, month, day = [int(i) for i in date_list[-1].split('-')]
        next_datetime = time_format(datetime.datetime(year, month, day, tzinfo=tz_utc), timedeltas={'days': 1}, opera=1)
        if next_datetime[:10] < end_date:
            date_list.append(next_datetime[:10])
        else:
            break
    date_list.append(end_date)
    return date_list
