# Date: 2025-09-20 23:42:00
# Description:

from decimal import Decimal


def to_precision_decimal(value, count=15):
    if isinstance(value, Decimal):
        return value
    if 'e-' in str(value) or 'E-' in str(value):
        float_v, e_num = str(value).split('-')
        if '.' in float_v:
            number_v, f = float_v[:-1].split('.')
        else:
            number_v, f = float_v[:-1], ''
        e_num = int(e_num)
        if e_num - len(number_v) > 0:
            new_value = '0.' + '0' * (e_num - len(number_v)) + number_v + f
        else:
            new_value = number_v[:-e_num] + '.' + number_v[-e_num:] + f
        i_f = new_value.split('.')
    elif 'e+' in str(value) or 'E+' in str(value):
        float_v, e_num = str(value).split('+')
        if '.' in float_v:
            number_v, f = float_v[:-1].split('.')
        else:
            number_v, f = float_v[:-1], ''
        e_num = int(e_num)
        if e_num - len(f) > 0:
            new_value = number_v + f[:e_num] + '0' * (e_num - len(f))
        else:
            new_value = number_v + f[:e_num] + '.' + f[e_num:]
        i_f = new_value.split('.')
    else:
        i_f = str(value).split('.')
    if len(i_f) == 1:
        result = i_f[0]
    else:
        result = "{}.{}".format(i_f[0], i_f[1][:count])
    return Decimal(result)


def to_precision_float(value, count=15):
    if 'e-' in str(value) or 'E-' in str(value):
        float_v, e_num = str(value).split('-')
        if '.' in float_v:
            number_v, f = float_v[:-1].split('.')
        else:
            number_v, f = float_v[:-1], ''
        e_num = int(e_num)
        if e_num - len(number_v) > 0:
            new_value = '0.' + '0' * (e_num - len(number_v)) + number_v + f
        else:
            new_value = number_v[:-e_num] + '.' + number_v[-e_num:] + f
        i_f = new_value.split('.')
    elif 'e+' in str(value) or 'E+' in str(value):
        float_v, e_num = str(value).split('+')
        if '.' in float_v:
            number_v, f = float_v[:-1].split('.')
        else:
            number_v, f = float_v[:-1], ''
        e_num = int(e_num)
        if e_num - len(f) > 0:
            new_value = number_v + f[:e_num] + '0' * (e_num - len(f))
        else:
            new_value = number_v + f[:e_num] + '.' + f[e_num:]
        i_f = new_value.split('.')
    else:
        i_f = str(value).split('.')
    if len(i_f) == 1:
        result = i_f[0]
    else:
        result = "{}.{}".format(i_f[0], i_f[1][:count])
    return float(result)
