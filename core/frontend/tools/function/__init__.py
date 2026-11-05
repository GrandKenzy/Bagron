"""Function-analysis package with a compatibility facade.

The implementation remains in ``_implementation`` during this conservative
extraction. Keeping this module as the public boundary preserves imports such
as ``core.frontend.tools.function`` while allowing the implementation to be
split into focused modules incrementally.
"""

from __future__ import annotations

from typing import Any

from . import _implementation

__all__ = _implementation.__all__


def __getattr__(name: str) -> Any:
    """Delegate public and legacy private helpers to the implementation.

    Some frontend tools intentionally reuse private signature helpers. The
    delegation keeps those existing imports working until those helpers are
    extracted into dedicated internal modules.
    """

    try:
        return getattr(_implementation, name)
    except AttributeError as error:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from error


def __dir__() -> list[str]:
    """Expose facade names together with implementation compatibility names."""

    return sorted(set(globals()) | set(dir(_implementation)))
