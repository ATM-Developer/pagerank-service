# -*- encoding: utf-8 -*-

from decimal import Decimal
from collections import defaultdict


DAILY_POOL = Decimal(1)


def algo_signed_sum_pr(records, default_coin):
    totals = defaultdict(Decimal)
    for r in records:
        amount = Decimal(str(r['amount']))
        totals[r['to']] += amount if r['is_credit'] else -amount
    return {default_coin: dict(totals)}


def algo_signed_sum_pool(records, default_coin):
    return {default_coin: DAILY_POOL}


def algo_signed_sum_reward(pr_totals, pool, default_coin):
    result = {}
    for coin, addr_amounts in pr_totals.items():
        coin_pool = pool.get(coin, Decimal(0))
        total_credits = sum(amount for amount in addr_amounts.values() if amount > 0)
        scale = Decimal(1) if total_credits <= coin_pool or total_credits == 0 else coin_pool / total_credits
        result[coin] = {
            address: (min(amount * scale, amount) if amount > 0 else amount)
            for address, amount in addr_amounts.items()
        }
    return result
