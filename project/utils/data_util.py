import os
import json
from collections import OrderedDict
from project.extensions import app_config
from project.utils.date_util import timestamp_to_format2, datetime_to_timestamp, get_dates_list


class SaveData():
    def __init__(self, web3eth, items, data_dir, prefix, start_blocknu, end_blocknu, block_interval, logger):
        self.web3eth = web3eth
        self.items = items
        self.data_dir = data_dir
        self.prefix = prefix
        self.start_block_number = start_blocknu
        self.end_block_number = end_blocknu
        self.block_interval = block_interval
        self.other_hour = app_config.OTHER_HOUR
        self.other_minute = app_config.OTHER_MINUTE
        self.logger = logger

    def _get_belong_date(self, block_number=None, timestamp=None):
        if block_number is not None:
            block_info = self.web3eth.get_block_by_number(block_number)
            block_timestamp = block_info['timestamp']
        else:
            block_timestamp = timestamp
        block_datetime = timestamp_to_format2(block_timestamp)
        belong_date = block_datetime[:10]
        if block_timestamp > datetime_to_timestamp(
                '{} {}:{}:00'.format(belong_date, self.other_hour, self.other_minute)):
            belong_date = timestamp_to_format2(block_timestamp, timedeltas={'days': 1}, opera=1)[:10]
        return belong_date, block_timestamp

    def __get_this_interval(self, end_timestamp, block_info):
        value = (end_timestamp - block_info['timestamp']) / 60 * self.block_interval
        if abs(value) < 1:
            value = -1 if value < 0 else 1
        return value

    def __get_end_blocknu(self, start_blocknu, end_timestamp, block_interval):
        self.block_interval = block_interval
        start_block_info = self.web3eth.get_block_by_number(start_blocknu)
        end_blocknu = int(start_blocknu + self.__get_this_interval(end_timestamp, start_block_info))
        end_block_info = self.web3eth.get_block_by_number(end_blocknu)
        closer_block_number = end_blocknu
        closer_timestamp = abs(end_timestamp - end_block_info['timestamp'])
        while abs(end_timestamp - end_block_info['timestamp']) > 120:
            self.logger.info('{} {} {}'.format(end_blocknu, end_block_info['timestamp'],
                                               timestamp_to_format2(end_block_info['timestamp'])))
            end_blocknu = int(end_blocknu + self.__get_this_interval(end_timestamp, end_block_info))
            end_block_info_n = self.web3eth.get_block_by_number(end_blocknu)
            if end_block_info_n:
                end_block_info = end_block_info_n
                this_closer_timestamp = abs(end_timestamp - end_block_info['timestamp'])
                if this_closer_timestamp < closer_timestamp:
                    closer_block_number = end_blocknu
                    closer_timestamp = this_closer_timestamp
            else:
                end_blocknu = closer_block_number
                end_block_info = self.web3eth.get_block_by_number(end_blocknu)
                break
        self.logger.info('end block number: {}, info: {}'.format(end_blocknu, end_block_info))
        if end_block_info['timestamp'] > end_timestamp:
            compare_type = '<'
            opera = range(end_blocknu, 0, -1)
        else:
            compare_type = '>'
            opera = range(end_blocknu, end_blocknu + 1000000)
        target_blocknu = end_blocknu
        for block_number in opera:
            block_number_info = self.web3eth.get_block_by_number(block_number)
            this_timestamp = block_number_info['timestamp']
            self.logger.info('{} {} {}'.format(block_number, this_timestamp, timestamp_to_format2(this_timestamp)))
            if compare_type == '<':
                if this_timestamp <= end_timestamp:
                    target_blocknu = block_number
                    break
            else:
                if this_timestamp <= end_timestamp:
                    target_blocknu = block_number
                else:
                    break
        return target_blocknu

    def get_block_interval(self, start_block_timestamp, end_block_timestamp):
        # interval per minute
        interval = (self.end_block_number - self.start_block_number) / \
                   (end_block_timestamp - start_block_timestamp) * 60
        self.logger.info('block interval : {}'.format(interval))
        return interval

    def save_to_file(self):
        if self.items:
            data_dates = OrderedDict()
            for item in self.items:
                try:
                    data_dates[self._get_belong_date(None, item['_time'])[0]].append(item)
                except:
                    data_dates[self._get_belong_date(None, item['_time'])[0]] = [item]
            launch_date = app_config.CHAINS.get(self.prefix, {}).get('LAUNCH_DATE')
            for date, data in data_dates.items():
                if launch_date and date < launch_date:
                    date = launch_date
                with open(os.path.join(self.data_dir, '{}_{}.txt'.format(self.prefix, date)), 'a') as wf:
                    for d in data:
                        wf.write('{}\n'.format(json.dumps(d)))
        start_date, start_block_timestamp = self._get_belong_date(self.start_block_number)
        end_date, end_block_timestamp = self._get_belong_date(self.end_block_number)
        dates_list = get_dates_list(start_date, end_date)
        for dl in dates_list:
            f1 = open(os.path.join(self.data_dir, '{}_{}.txt'.format(self.prefix, dl)), 'a')
            f1.close()
        start_timestamp = datetime_to_timestamp('{} {}:{}:00'.format(start_date, self.other_hour, self.other_minute))
        if start_date != end_date \
                or (start_block_timestamp > start_timestamp
                    and not os.path.exists(
                    os.path.join(self.data_dir, '{}_{}_end_block.txt'.format(self.prefix, start_date)))):
            block_interval = self.get_block_interval(start_block_timestamp, end_block_timestamp)
            start_blocknu = self.start_block_number
            for date in dates_list[:-1]:
                date_end_blocknu_file_name = '{}_{}_end_block.txt'.format(self.prefix, date)
                date_end_blocknu_file = os.path.join(self.data_dir, date_end_blocknu_file_name)
                end_timestamp = datetime_to_timestamp('{} {}:{}:00'.format(date, self.other_hour, self.other_minute))
                date_end_blocknu = self.__get_end_blocknu(start_blocknu, end_timestamp, block_interval)
                with open(date_end_blocknu_file, 'w') as wf:
                    wf.write(json.dumps({'block': date_end_blocknu}))
                start_blocknu = date_end_blocknu
        return True
