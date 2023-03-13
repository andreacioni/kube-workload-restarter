import re


def parse_duration(duration_str):
    match = re.match(r'(\d+)([a-z]+)', duration_str, re.IGNORECASE)
    if not match:
        raise ValueError('Invalid duration string: {}'.format(duration_str))
    value, unit = match.groups()
    unit = unit.lower()
    if unit == 'h':
        value = int(value) * 3600
    elif unit == 'm':
        value = int(value) * 60
    elif unit == 'd':
        value = int(value) * 3600 * 24
    else:
        raise ValueError('Invalid duration unit: {}'.format(unit))
    return value
