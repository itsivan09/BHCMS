from collections.abc import Callable
from typing import TypeVar

from app import app

T = TypeVar('T')


def run_in_app_context(fn: Callable[[], T]) -> T:
    with app.app_context():
        return fn()
