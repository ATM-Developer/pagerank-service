from decimal import Decimal

from project.models.enums import ChainDataType
from project.utils.date_util import get_now_timestamp
from project.utils.date_util import timestamp_to_format2


# pledge records
class TbUserPledge():
    def __init__(self, stake_num, event, block_number, user_address, node_address, amount, _time):
        self.stake_num = stake_num
        self.date = timestamp_to_format2(_time)
        self.event = event
        self.block_number = block_number
        self.user_address = user_address
        self.node_address = node_address
        self.amount = str(amount)
        self._time = _time

    def to_dict(self):
        return self.__dict__


class TbTransferEvent():
    def __init__(self, log_index, from_addr, to_addr, value, event_time, transaction_index, transaction_hash, address,
                 block_hash, block_number):
        self.log_index = log_index
        self.from_addr = from_addr
        self.to_addr = to_addr
        self.value = value
        self.timestamp = event_time
        self.date_time = timestamp_to_format2(self.timestamp)
        self.transaction_index = transaction_index
        self.transaction_hash = transaction_hash
        self.address = address
        self.block_hash = block_hash
        self.block_number = block_number

    def to_dict(self):
        return self.__dict__


class TbEaringsAccountBook:
    def __init__(self, user_id, coin_type, earnings_type, amount):
        self.user_id = user_id
        self.data_type = ChainDataType.EARNINGS.value
        self.coin_type = coin_type
        self.earnings_type = earnings_type
        self.amount = amount

    def to_dict(self):
        return self.__dict__


class TbPrefetchingAccountBook:
    def __init__(self, user_id, coin_type, overdue_timestamps, nonce, amount_from_pr=0, amount_from_server=0,
                 amount_from_pledge=0, amount_from_transfer=0, net_pr=0, alone_pr=0):
        self.user_id = user_id
        self.data_type = ChainDataType.PREFETCHING.value
        self.coin_type = coin_type
        self.overdue_timestamps = overdue_timestamps
        self.nonce = nonce
        self.from_pr = amount_from_pr
        self.from_pledge = amount_from_pledge
        self.from_server = amount_from_server
        self.from_liquidity = amount_from_transfer
        self.from_net_pr = net_pr
        self.from_alone_pr = alone_pr
        self.total_amount = Decimal(str(self.from_pr)) + Decimal(str(self.from_server)) + \
                            Decimal(str(self.from_pledge)) + Decimal(str(self.from_liquidity)) + \
                            Decimal(str(self.from_net_pr)) + Decimal(str(self.from_alone_pr))
        self.timestamps = get_now_timestamp()

    def to_dict(self):
        return self.__dict__


class TbExtractAccountBook():
    def __init__(self, user_id, coin_type, overdue_timestamps, nonce, amount_from_pr=0, amount_from_server=0,
                 amount_from_pledge=0, amount_from_transfer=0, net_pr=0, alone_pr=0, transaction_hash=None):
        self.user_id = user_id
        self.data_type = ChainDataType.EXTRACT.value
        self.coin_type = coin_type
        self.overdue_timestamps = overdue_timestamps
        self.nonce = nonce
        self.from_pr = amount_from_pr
        self.from_pledge = amount_from_pledge
        self.from_server = amount_from_server
        self.from_liquidity = amount_from_transfer
        self.from_net_pr = net_pr
        self.from_alone_pr = alone_pr
        self.total_amount = Decimal(str(self.from_pr)) + Decimal(str(self.from_server)) + \
                            Decimal(str(self.from_pledge)) + Decimal(str(self.from_liquidity)) + \
                            Decimal(str(self.from_net_pr)) + Decimal(str(self.from_alone_pr))
        self.transaction_hash = transaction_hash
        self.timestamps = get_now_timestamp()

    def to_dict(self):
        return self.__dict__
