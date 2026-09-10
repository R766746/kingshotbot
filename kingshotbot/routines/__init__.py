"""Routine registry - importing the modules registers them."""

from .base import Routine, RoutineResult, ROUTINES, register
from . import daily, gather, build, gifts, events  # noqa: F401 (side effects)

__all__ = ["Routine", "RoutineResult", "ROUTINES", "register"]
