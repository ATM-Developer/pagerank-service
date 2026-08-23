# Date: 2025-09-20 23:42:00
# Description:

from decimal import Decimal, Context, ROUND_HALF_UP

# Local, explicit context so quantize() below never depends on whatever
# precision the caller's thread happens to have set on decimal.getcontext().
# prec=100 leaves headroom for on-chain amounts (up to ~1e30) plus `count`
# fractional digits without raising InvalidOperation.
_QUANTIZE_CONTEXT = Context(prec=100)


def _round_decimal(value, count):
    quantum = Decimal('1e-{}'.format(count))
    return Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP, context=_QUANTIZE_CONTEXT)


def to_precision_decimal(value, count=15):
    if isinstance(value, Decimal):
        return value
    return _round_decimal(value, count)


def to_precision_float(value, count=15):
    return float(_round_decimal(value, count))
