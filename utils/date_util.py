import pytz
from datetime import datetime, timedelta


def get_pagerank_date():
    tz = pytz.timezone('UTC')
    pagerank_time = datetime.now(tz)
    if pagerank_time >= datetime(pagerank_time.year, pagerank_time.month, pagerank_time.day, 14, 15, tzinfo=tz):
        pass
    else:
        pagerank_time = pagerank_time + timedelta(days=-1)
    pagerank_date = pagerank_time.strftime('%Y-%m-%d')
    return pagerank_date
