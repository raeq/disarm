"""Suite modules, one per external-artifact family."""

from __future__ import annotations

from . import (
    academic,
    comparators,
    cve,
    datasets,
    introspective,
    model_artifacts,
    normative,
)

MODULES = (normative, cve, academic, datasets, model_artifacts, comparators, introspective)

__all__ = [
    "MODULES",
    "academic",
    "comparators",
    "cve",
    "datasets",
    "introspective",
    "model_artifacts",
    "normative",
]
