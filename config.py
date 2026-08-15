"""Runtime configuration for the Custos gateway."""

from __future__ import annotations

import os


def env(name: str, default: str) -> str:
    return os.getenv(name, default)


STALENESS_THRESHOLD_HOURS = float(env("CUSTOS_STALENESS_HOURS", "24.0"))
DRIFT_THRESHOLD = float(env("CUSTOS_DRIFT_THRESHOLD", "0.02"))
BACKING_FLOOR = float(env("CUSTOS_BACKING_FLOOR", "1.0"))
MAX_OBSERVATION_AGE_DAYS = int(env("CUSTOS_MAX_OBS_AGE_DAYS", "4"))
ORACLE_TIMEOUT_SECONDS = float(env("CUSTOS_ORACLE_TIMEOUT", "3.0"))
ORACLE_CACHE_TTL_SECONDS = int(env("CUSTOS_CACHE_TTL", "60"))
ATTESTATION_TTL_SECONDS = int(env("CUSTOS_ATTESTATION_TTL", "300"))
FAIL_MODE = env("CUSTOS_FAIL_MODE", "closed")
