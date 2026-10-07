# -*- encoding: utf-8 -*-

from decimal import Decimal
from collections import defaultdict


def algo_no_cap_pr(records, default_coin):
    totals = defaultdict(Decimal)
    for r in records:
        amount = Decimal(str(r['amount']))
        totals[r['to']] += amount if r['is_credit'] else -amount
    return {default_coin: dict(totals)}


def algo_no_cap_pool(records, default_coin):
    return {}


def algo_no_cap_reward(pr_totals, pool, default_coin):
    return {coin: dict(addr_amounts) for coin, addr_amounts in pr_totals.items()}
