"""Rung registry. Each module exposes `generate(seed=None) -> Rung`."""
from sandbox.rungs import rung0, rung1, rung2, rung3

REGISTRY = {
    "0": rung0.generate,
    "rung0": rung0.generate,
    "1": rung1.generate,
    "rung1": rung1.generate,
    "2": rung2.generate,
    "rung2": rung2.generate,
    "3": rung3.generate,
    "rung3": rung3.generate,
}


def get(rung_id: str):
    if rung_id not in REGISTRY:
        raise KeyError(f"unknown rung {rung_id!r}; known: {sorted(REGISTRY)}")
    return REGISTRY[rung_id]
