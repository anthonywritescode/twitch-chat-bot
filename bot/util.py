def seconds_to_readable(seconds: int) -> str:
    parts = []
    for n, unit in (
            (60 * 60, 'hours'),
            (60, 'minutes'),
            (1, 'seconds'),
    ):
        if seconds // n:
            parts.append(f'{seconds // n} {unit}')
        seconds %= n
    return ', '.join(parts)
