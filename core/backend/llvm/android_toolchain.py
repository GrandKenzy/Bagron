"""Resolution of the Android NDK toolchain for explicit LLVM triples."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import platform
import re


class AndroidToolchainError(ValueError):
    """Raised when an Android triple or NDK installation is unusable."""


@dataclass(frozen=True)
class AndroidTarget:
    """Validated Android target identity."""

    triple: str
    architecture: str
    api_level: int


@dataclass(frozen=True)
class AndroidToolchain:
    """Tools and sysroot selected for one Android target."""

    target: AndroidTarget
    ndk_root: Path
    host_tag: str
    prebuilt_root: Path
    clang: Path
    ld_lld: Path
    sysroot: Path
    api_library_dir: Path

    @property
    def triple(self) -> str:
        return self.target.triple

    @property
    def api_level(self) -> int:
        return self.target.api_level

    @property
    def clang_target_args(self) -> tuple[str, ...]:
        """Arguments shared by compile, assemble and link invocations."""
        return (
            f'--target={self.target.triple}',
            f'--sysroot={self.sysroot}',
        )


_ANDROID_TRIPLE_RE = re.compile(
    r'^(?P<architecture>aarch64|x86_64)-linux-android(?P<api>[0-9]+)$'
)
_MIN_ANDROID_API = 21


def _parse_android_target(triple: str) -> AndroidTarget:
    normalized = str(triple).strip().lower()
    match = _ANDROID_TRIPLE_RE.fullmatch(normalized)
    if match is None:
        raise AndroidToolchainError(
            f'Triple Android no soportado: {triple!r}; usa '
            'aarch64-linux-android<api> o x86_64-linux-android<api>'
        )

    api_level = int(match.group('api'))
    if api_level < _MIN_ANDROID_API:
        raise AndroidToolchainError(
            f'API Android {api_level} no soportada para '
            f'{normalized!r}; el minimo para estos targets es '
            f'{_MIN_ANDROID_API}'
        )
    return AndroidTarget(
        triple=normalized,
        architecture=match.group('architecture'),
        api_level=api_level,
    )


def _host_tag_candidates() -> tuple[str, ...]:
    system = platform.system().strip().lower()
    machine = platform.machine().strip().lower()
    is_arm = machine in {'arm64', 'aarch64'}

    if system == 'windows':
        # The Windows NDK distribution is x86_64 and runs on ARM64 Windows
        # through the platform's native compatibility layer.
        return ('windows-x86_64',)
    if system == 'darwin':
        return ('darwin-arm64', 'darwin-x86_64') if is_arm else (
            'darwin-x86_64', 'darwin-arm64'
        )
    if system == 'linux':
        return ('linux-aarch64', 'linux-x86_64') if is_arm else (
            'linux-x86_64', 'linux-aarch64'
        )
    return ()


def _ndk_root_from_environment(ndk_home: str | Path | None) -> Path:
    raw = ndk_home
    if raw is None:
        raw = os.environ.get('ANDROID_NDK_HOME')
    if raw is None:
        raw = os.environ.get('ANDROID_NDK_ROOT')
    if raw is None or not str(raw).strip():
        raise AndroidToolchainError(
            'No se encontro ANDROID_NDK_HOME; configura la ruta del NDK '
            'antes de compilar para Android'
        )

    root = Path(raw).expanduser()
    if not root.is_dir():
        raise AndroidToolchainError(
            f'ANDROID_NDK_HOME no apunta a un directorio valido: {root}'
        )
    return root.resolve()


def _select_prebuilt(ndk_root: Path) -> tuple[str, Path]:
    prebuilt_parent = ndk_root / 'toolchains' / 'llvm' / 'prebuilt'
    if not prebuilt_parent.is_dir():
        raise AndroidToolchainError(
            f'El NDK no contiene sus toolchains LLVM: {prebuilt_parent}'
        )

    for host_tag in _host_tag_candidates():
        prebuilt_root = prebuilt_parent / host_tag
        if (
            (prebuilt_root / 'bin' / 'clang').is_file()
            or (prebuilt_root / 'bin' / 'clang.exe').is_file()
        ) and (
            (prebuilt_root / 'bin' / 'ld.lld').is_file()
            or (prebuilt_root / 'bin' / 'ld.lld.exe').is_file()
        ):
            return host_tag, prebuilt_root

    candidates = ', '.join(path.name for path in prebuilt_parent.iterdir())
    raise AndroidToolchainError(
        f'No hay un prebuilt LLVM del NDK para este host; encontrados: '
        f'{candidates or "ninguno"}'
    )


def _tool_path(prebuilt_root: Path, name: str) -> Path:
    bin_dir = prebuilt_root / 'bin'
    for candidate in (bin_dir / name, bin_dir / f'{name}.exe'):
        if candidate.is_file():
            return candidate
    raise AndroidToolchainError(
        f'El prebuilt LLVM no contiene la herramienta requerida: {bin_dir / name}'
    )


def resolve_android_toolchain(
    triple: str,
    *,
    ndk_home: str | Path | None = None,
) -> AndroidToolchain:
    """Resolve clang, ld.lld and the API-specific sysroot for one triple."""
    target = _parse_android_target(triple)
    ndk_root = _ndk_root_from_environment(ndk_home)
    host_tag, prebuilt_root = _select_prebuilt(ndk_root)
    clang = _tool_path(prebuilt_root, 'clang')
    ld_lld = _tool_path(prebuilt_root, 'ld.lld')
    sysroot = prebuilt_root / 'sysroot'
    # The NDK keeps the API level below the ABI library triple without the
    # numeric API suffix used by the compiler target triple.
    library_triple = f'{target.architecture}-linux-android'
    api_library_dir = (
        sysroot / 'usr' / 'lib' / library_triple / str(target.api_level)
    )

    if not sysroot.is_dir():
        raise AndroidToolchainError(
            f'El NDK no contiene el sysroot LLVM esperado: {sysroot}'
        )
    if not api_library_dir.is_dir():
        raise AndroidToolchainError(
            f'El NDK no contiene bibliotecas para {target.triple}: '
            f'{api_library_dir}'
        )

    return AndroidToolchain(
        target=target,
        ndk_root=ndk_root,
        host_tag=host_tag,
        prebuilt_root=prebuilt_root,
        clang=clang,
        ld_lld=ld_lld,
        sysroot=sysroot,
        api_library_dir=api_library_dir,
    )


__all__ = [
    'AndroidTarget',
    'AndroidToolchain',
    'AndroidToolchainError',
    'resolve_android_toolchain',
]
