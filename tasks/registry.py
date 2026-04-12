"""Task registry — maps dataset names to TaskLoader instances.

Usage:
    from tasks.registry import REGISTRY
    loader = REGISTRY["gsm8k"]
    tasks = loader.load(limit=10)

New datasets: add an entry here after implementing a TaskLoader subclass.
"""

from __future__ import annotations

from tasks.gsm8k import GSM8KLoader
from tasks.loader import TaskLoader

REGISTRY: dict[str, TaskLoader] = {
    "gsm8k": GSM8KLoader(),
}
