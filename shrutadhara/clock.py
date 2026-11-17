"""Suspend-aware elapsed session time; UTC timestamps remain presentation data."""

import time
from pathlib import Path


def elapsed_time() -> float:
    return time.clock_gettime(time.CLOCK_BOOTTIME)


def boot_identity() -> str:
    return Path("/proc/sys/kernel/random/boot_id").read_text().strip()
