from __future__ import annotations

from dataclasses import dataclass

from llvmlite import binding as llvm


class TargetResolutionError(ValueError):
    """Raised when Bagron's Arch clause cannot resolve to an LLVM target."""


_ARCH_ALIASES = {
    'x86': 'i386',
    'amd': 'x86_64',
    'arm': 'aarch64',
}


@dataclass(frozen=True)
class TargetHandle:
    request: str
    triple: str
    target: object
    machine: object

    @property
    def pointer_size(self) -> int:
        return 4 if self.triple.split('-', 1)[0] in {'i386', 'i686', 'x86'} else 8


def initialize_llvm() -> None:
    """Initialize target registries once for the current process."""
    if getattr(initialize_llvm, '_done', False):
        return

    llvm.initialize_all_targets()
    llvm.initialize_all_asmprinters()
    llvm.initialize_native_target()
    llvm.initialize_native_asmprinter()
    initialize_llvm._done = True  # type: ignore[attr-defined]


def _triple_for_request(request: str, host_triple: str) -> str:
    if request == 'auto':
        return host_triple

    if '-' in request:
        return request

    architecture = _ARCH_ALIASES.get(request)
    if architecture is None:
        raise TargetResolutionError(
            f"Target Arch invalido: {request!r}. Use 'auto', 'x86', 'amd', 'arm' o un triple LLVM."
        )

    parts = host_triple.split('-')
    parts[0] = architecture
    return '-'.join(parts)


def resolve_target(request: str | None = None) -> TargetHandle:
    initialize_llvm()
    normalized = str(request or 'auto').strip().lower()
    host_triple = llvm.get_default_triple()
    triple = _triple_for_request(normalized, host_triple)

    try:
        target = llvm.Target.from_triple(triple)
        machine = target.create_target_machine()
    except (RuntimeError, ValueError) as error:
        raise TargetResolutionError(
            f'No se pudo resolver el target LLVM {triple!r}: {error}'
        ) from error

    return TargetHandle(
        request=normalized,
        triple=triple,
        target=target,
        machine=machine,
    )
