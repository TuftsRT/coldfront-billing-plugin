def first_or_none(sequence):
    return sequence[0] if sequence else None


def parse_float(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
