import re
from datetime import datetime, time, timedelta

from django.utils import timezone
from email_validator import EmailNotValidError, validate_email


def first_or_none(sequence):
    return sequence[0] if sequence else None


def parse_float(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def get_month_abbr():
    return datetime.now().strftime('%b').upper()


def validate_emails(emails_str: str) -> tuple[list[str], list[str]]:
    """
    Split a string of addresses (semicolon or comma separated), validate each,
    and return (normalized_unique_in_order, invalid_original_parts).
    """
    email_to = re.split(r'[;,]', emails_str)

    valid_recipients: list[str] = []
    seen: set[str] = set()
    invalid_recipients: list[str] = []

    for email in email_to:
        email = email.strip()
        if not email:
            continue
        try:
            valid = validate_email(email)
            addr = valid.normalized
        except EmailNotValidError:
            invalid_recipients.append(email)
            continue
        if addr not in seen:
            seen.add(addr)
            valid_recipients.append(addr)

    return valid_recipients, invalid_recipients


def calculate_next_run_date_monthly(start_date: datetime, hour) -> datetime:
    next_run = datetime.combine(start_date, time(hour=hour, minute=0))
    return timezone.make_aware(next_run, timezone.get_default_timezone())


def calculate_next_run_date_n_minutes(minutes: int) -> datetime:
    return timezone.localtime(timezone.now() + timedelta(minutes=minutes))


def calculate_next_run(
    start_date: datetime,
    hour: int | None = None,
    minutes: int | None = None,
) -> datetime:
    if hour is not None:
        return calculate_next_run_date_monthly(
            start_date=start_date,
            hour=hour,
        )
    if minutes is not None:
        return calculate_next_run_date_n_minutes(minutes=minutes)
    raise ValueError('Either hour or minutes must be provided')


class NoStorageException(Exception):
    pass


def elide_middle(text: str, max_length: int = 20, marker: str = '...') -> str:
    if len(text) <= max_length:
        return text
    if max_length < len(marker) + 2:
        raise ValueError('max_length must be at least len(marker) + 2')

    marker_len = len(marker)
    chars_left = (max_length - marker_len + 1) // 2
    chars_right = (max_length - marker_len) // 2

    start = text[:chars_left]
    end = text[-chars_right:] if chars_right > 0 else ''

    return f'{start}{marker}{end}'


def sanitize_csv_value(value: str) -> str:
    """
    Sanitize a value for CSV output by escaping quotes and wrapping in quotes if necessary.
    """
    if not isinstance(value, str):
        value = str(value)
    value = value.strip()
    for i in ['=', '+', '-', '@', '|']:
        if value.startswith(i):
            value = f"'{value}"
    if '"' in value or ',' in value:
        value = value.replace('"', '""')
        return f'"{value}"'
    return value
