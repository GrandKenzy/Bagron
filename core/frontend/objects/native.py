from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NativeInclude:
    """Native header and library requested by a Bagron module."""

    header: str
    library: str


__all__ = ['NativeInclude']
