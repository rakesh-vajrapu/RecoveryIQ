"""Semantic keyed randomness for counterfactual and incident membership stability."""

from __future__ import annotations

import hashlib


def keyed_uniform(seed: int, namespace: str, *identifiers: object) -> float:
    payload = "|".join((str(seed), namespace, *(str(value) for value in identifiers)))
    digest = hashlib.sha256(payload.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / 2**64
