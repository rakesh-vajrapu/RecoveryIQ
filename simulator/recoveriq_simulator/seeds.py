"""Pre-registered, non-overlapping seed groups for methodological discipline."""

from __future__ import annotations

DEVELOPMENT_SEEDS = tuple(range(20_260_901, 20_260_911))
VALIDATION_SEEDS = tuple(range(20_261_001, 20_261_011))
FINAL_EVALUATION_SEEDS = tuple(range(20_261_101, 20_261_121))

SEED_GROUPS: dict[str, tuple[int, ...]] = {
    "development": DEVELOPMENT_SEEDS,
    "validation": VALIDATION_SEEDS,
    "robustness": DEVELOPMENT_SEEDS + VALIDATION_SEEDS,
    "final": FINAL_EVALUATION_SEEDS,
}


def seeds_for_group(group: str) -> tuple[int, ...]:
    try:
        return SEED_GROUPS[group]
    except KeyError as error:
        choices = ", ".join(sorted(SEED_GROUPS))
        raise ValueError(f"unknown seed group {group!r}; choose one of: {choices}") from error
