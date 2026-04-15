import re
from datetime import datetime

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


class NoStorageException(Exception):
    pass
