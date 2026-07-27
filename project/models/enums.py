from enum import Enum, unique


@unique
class ResponseCode(Enum):
    SUCCESS = 0, 'success'
    PARAMS_ERROR = 202, 'params error.'
    OPERATION_FAIL = 203, 'operation failure.'
    NOT_EXECUTER = 204, 'not executer'
    NOT_SENATORS = 205, 'not senators'
    PLEASE_WAIT = 206, 'please wait'

    ONLY_INT = 301, 'amount only is int'


@unique
class EarningsType(Enum):
    SERVER = 'server'
    PLEDGE = 'pledge'
    PR = 'main_pr'
    TRANSFER = 'liquidity'
    NET_PR = 'net_pr'
    ALONE_PR = 'alone_pr'


@unique
class ChainDataType(Enum):
    EARNINGS = 'earnings'
    PREFETCHING = 'prefetching'
    EXTRACT = 'extract'
