# -*- encoding: utf-8 -*-

from project.configs.voucher.voucher_algos.signed_sum import (
    algo_signed_sum_pr, algo_signed_sum_pool, algo_signed_sum_reward,
)
from project.configs.voucher.voucher_algos.no_cap import (
    algo_no_cap_pr, algo_no_cap_pool, algo_no_cap_reward,
)

VOUCHER_REWARD_GROUPS = [
    {'name': 'default_points', 'voucher_types': [0], 'mode': 0, 'coin': 'luca'},
    # {'name': 'instant_bonus_points', 'voucher_types': [1], 'mode': 0, 'coin': 'luca'},
]

VOUCHER_GROUP_ALGOS = {
    'default_points': (algo_signed_sum_pr, algo_signed_sum_pool, algo_signed_sum_reward),
    # 'instant_bonus_points': (algo_no_cap_pr, algo_no_cap_pool, algo_no_cap_reward),
}
