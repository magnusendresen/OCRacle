from datetime import datetime
from time import perf_counter
from contextlib import contextmanager

def log(message: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] --- {message}")


@contextmanager
def timer(name: str):
    """Context manager for timing code blocks."""
    start = perf_counter()
    try:
        yield
    finally:
        duration = perf_counter() - start
        log(f"{name} completed in {duration:.2f}s")

