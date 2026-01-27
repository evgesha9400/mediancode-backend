import datetime


def generate_string(index: int, prefix: str) -> str:
    return f"{prefix} {index}"


def generate_int(index: int, multiplier: int) -> int:
    return index * multiplier


def generate_bool(index: int) -> bool:
    return bool(index)


def generate_float(index: int, multiplier: float) -> float:
    return float(index) * multiplier


def generate_datetime(index: int) -> str:
    """Generate an ISO format datetime string placeholder.

    Returns a string like "2026-01-27T00:00:06" that can be used directly
    in generated code without requiring datetime imports.
    """
    assert index <= 86400, "Index is too large, should be less than 86400"
    now = datetime.datetime.now(datetime.UTC)
    year = now.year
    month = now.month
    day = now.day
    hour = 0
    minute = 0
    second = index

    # Increment minutes if seconds exceed 60
    minute += second // 60
    second = second % 60

    # Increment hours if minutes exceed 60
    hour += minute // 60
    minute = minute % 60

    return f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:{second:02d}"
