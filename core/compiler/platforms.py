"""Host-platform discovery and target-option policy for Bagron.

This module deliberately separates what Python can identify from what Bagron
can currently compile. LLVM target resolution remains in the backend.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import platform
import re
import sys


class PlatformOptionError(ValueError):
    """Raised when a platform or architecture option cannot be accepted."""


@dataclass(frozen=True)
class HostPlatform:
    """Canonical host facts collected from Python's platform module."""

    system: str
    architecture: str
    bitness: str
    raw_system: str
    raw_architecture: str
    python_platform: str


_SYSTEM_ALIASES = {
    'win32': 'windows',
    'win64': 'windows',
    'windows': 'windows',
    'nt': 'windows',
    'cygwin': 'cygwin',
    'msys': 'msys',
    'linux': 'linux',
    'gnu/linux': 'linux',
    'android': 'android',
    'darwin': 'darwin',
    'mac': 'darwin',
    'macos': 'darwin',
    'osx': 'darwin',
    'ios': 'ios',
    'freebsd': 'freebsd',
    'openbsd': 'openbsd',
    'netbsd': 'netbsd',
    'dragonfly': 'dragonfly',
    'aix': 'aix',
    'sunos': 'sunos',
    'solaris': 'sunos',
    'haiku': 'haiku',
    'emscripten': 'emscripten',
    'wasi': 'wasi',
    'java': 'java',
}

# Recognition does not grant compilation support.
_KNOWN_SYSTEMS = frozenset({
    'windows', 'linux', 'android', 'darwin', 'ios', 'freebsd', 'openbsd',
    'netbsd', 'dragonfly', 'aix', 'sunos', 'haiku', 'emscripten', 'wasi',
    'java', 'cygwin', 'msys', 'baremetal',
})
_SUPPORTED_SYSTEMS = frozenset({'windows', 'linux', 'android', 'baremetal'})

_ARCHITECTURE_ALIASES = {
    'amd': 'x86_64',
    'amd64': 'x86_64',
    'x64': 'x86_64',
    'x86_64': 'x86_64',
    'x86': 'i386',
    'i386': 'i386',
    'i486': 'i386',
    'i586': 'i386',
    'i686': 'i386',
    # Preserve Bagron's existing ``arm`` alias semantics.
    'arm': 'aarch64',
    'arm64': 'aarch64',
    'aarch64': 'aarch64',
    'armv8l': 'aarch64',
    'armv7': 'armv7',
    'armv7l': 'armv7',
    'armv6': 'armv6',
    'armv6l': 'armv6',
    'riscv32': 'riscv32',
    'riscv64': 'riscv64',
    'ppc': 'ppc',
    'ppc64': 'ppc64',
    'ppc64le': 'ppc64le',
    'powerpc': 'ppc',
    'powerpc64': 'ppc64',
    'powerpc64le': 'ppc64le',
    's390x': 's390x',
    'mips': 'mips',
    'mips64': 'mips64',
    'wasm32': 'wasm32',
    'wasm64': 'wasm64',
}
_KNOWN_ARCHITECTURES = frozenset(_ARCHITECTURE_ALIASES.values())
_SUPPORTED_ARCHITECTURES = frozenset({
    'x86_64', 'i386', 'aarch64', 'riscv32', 'riscv64',
})
_ARCHITECTURE_BITS = {
    'x86_64': '64',
    'i386': '32',
    'aarch64': '64',
    'armv7': '32',
    'armv6': '32',
    'riscv32': '32',
    'riscv64': '64',
    'ppc': '32',
    'ppc64': '64',
    'ppc64le': '64',
    's390x': '64',
    'mips': '32',
    'mips64': '64',
    'wasm32': '32',
    'wasm64': '64',
}


def _slug(value: object) -> str:
    normalized = re.sub(r'[^a-z0-9]+', '-', str(value).strip().lower())
    return normalized.strip('-')


def normalize_system(value: object) -> str:
    """Return a canonical system name without deciding support."""
    raw = str(value).strip().lower()
    if raw == 'auto':
        return 'auto'
    if not raw:
        raise PlatformOptionError('El sistema no puede estar vacio')
    return _SYSTEM_ALIASES.get(raw, _slug(raw))


def normalize_architecture(value: object) -> str:
    """Normalize an architecture alias while preserving an LLVM triple tail."""
    raw = str(value).strip().lower()
    if raw == 'auto':
        return 'auto'
    if not raw:
        raise PlatformOptionError('La arquitectura no puede estar vacia')

    head, separator, tail = raw.partition('-')
    normalized_head = _ARCHITECTURE_ALIASES.get(head, _slug(head))
    return normalized_head + (f'-{tail}' if separator else '')


def architecture_name(value: object) -> str:
    """Return the canonical architecture component of an alias or triple."""
    return normalize_architecture(value).split('-', 1)[0]


def architecture_bits(value: object) -> str:
    """Return the canonical pointer width for an architecture or LLVM triple."""
    return _ARCHITECTURE_BITS.get(architecture_name(value), 'unknown')


def detect_host_system() -> str:
    """Detect the host system and distinguish Android from generic Linux."""
    info = platform.uname()
    raw_system = str(platform.system() or getattr(info, 'system', '')).strip()
    system_name = normalize_system(raw_system or sys.platform)
    signals = (
        raw_system,
        str(getattr(info, 'system', '')),
        str(platform.platform()),
        str(platform.release()),
        sys.platform,
    )
    if system_name == 'linux' and any(
        'android' in signal.lower() for signal in signals if signal
    ):
        return 'android'
    if system_name == 'linux' and (
        os.environ.get('ANDROID_ROOT')
        or os.environ.get('ANDROID_DATA')
        or Path('/system/build.prop').is_file()
        or Path('/system/bin/getprop').is_file()
    ):
        return 'android'
    return system_name


def detect_host_platform() -> HostPlatform:
    """Collect canonical host system, architecture and bitness facts."""
    info = platform.uname()
    raw_system = str(platform.system() or getattr(info, 'system', '')).strip()
    raw_architecture = str(
        platform.machine() or getattr(info, 'machine', '') or 'unknown'
    ).strip()
    bitness = str(platform.architecture()[0] or 'unknown').strip().lower()
    return HostPlatform(
        system=detect_host_system(),
        architecture=architecture_name(raw_architecture),
        bitness=bitness,
        raw_system=raw_system or sys.platform,
        raw_architecture=raw_architecture,
        python_platform=sys.platform,
    )


def validate_system_option(value: object) -> str:
    """Validate a System clause and return its canonical supported name."""
    canonical = (
        detect_host_system()
        if str(value).strip().lower() == 'auto'
        else normalize_system(value)
    )
    if canonical not in _KNOWN_SYSTEMS:
        raise PlatformOptionError(
            f'La clausula System posee un valor invalido: {value!r}'
        )
    if canonical not in _SUPPORTED_SYSTEMS:
        raise PlatformOptionError(
            f'El sistema {canonical!r} es reconocido, pero aun no esta '
            'soportado por Bagron'
        )
    return canonical


def validate_architecture_option(value: object) -> str:
    """Validate an Arch alias or LLVM triple against backend support."""
    canonical = (
        detect_host_platform().architecture
        if str(value).strip().lower() == 'auto'
        else normalize_architecture(value)
    )
    base = canonical.split('-', 1)[0]
    if base not in _KNOWN_ARCHITECTURES:
        raise PlatformOptionError(
            f'La arquitectura {value!r} posee un valor invalido'
        )
    if base not in _SUPPORTED_ARCHITECTURES:
        raise PlatformOptionError(
            f'La arquitectura {base!r} es reconocida, pero aun no esta '
            'soportada por Bagron'
        )
    return canonical


def supported_systems() -> frozenset[str]:
    return _SUPPORTED_SYSTEMS


def supported_architectures() -> frozenset[str]:
    return _SUPPORTED_ARCHITECTURES


__all__ = [
    'HostPlatform',
    'PlatformOptionError',
    'architecture_bits',
    'architecture_name',
    'detect_host_platform',
    'detect_host_system',
    'normalize_architecture',
    'normalize_system',
    'supported_architectures',
    'supported_systems',
    'validate_architecture_option',
    'validate_system_option',
]
