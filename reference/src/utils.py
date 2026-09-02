import time

def minutes_in_ms(minutes: float | int) -> int:
    return round(minutes * 60_000)

def seconds_in_ms(seconds: float | int) -> int:
    return round(seconds * 1000)


def batched(iterable, n: int) -> list:
    """Split an iterable into batches of given size."""
    items = list(iterable)
    return [items[i:i + n] for i in range(0, len(items), n)]


def now_ms() -> int:
    """Get current time in milliseconds since epoch."""
    return round(time.time() * 1000)
