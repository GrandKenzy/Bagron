from __future__ import annotations

from dataclasses import dataclass

from llvmlite import binding as llvm


class TargetResolutionError(ValueError):
    """Raised when Bagron's Arch clause cannot resolve to an LLVM target."""


_ARCH_ALIASES = {
    'x86': 'i386',
    'i386': 'i386',
    'i686': 'i386',
    'amd': 'x86_64',
    'amd64': 'x86_64',
    'x86_64': 'x86_64',
    'arm': 'aarch64',
    'arm64': 'aarch64',
    'aarch64': 'aarch64',
    'riscv32': 'riscv32',
    'riscv64': 'riscv64',
}


@dataclass(frozen=True)
class TargetHandle:
    request: str
    triple: str
    target: object
    machine: object

    @property
    def pointer_size(self) -> int:
        architecture = self.triple.split('-', 1)[0].lower()
        return 4 if architecture in {
            'i386', 'i686', 'x86', 'arm', 'armv6', 'armv7',
            'thumb', 'riscv32',
        } else 8


def initialize_llvm() -> None:
    """Initialize target registries once for the current process."""
    if getattr(initialize_llvm, '_done', False):
        return

    llvm.initialize_all_targets()
    llvm.initialize_all_asmprinters()
    llvm.initialize_native_target()
    llvm.initialize_native_asmprinter()
    initialize_llvm._done = True  # type: ignore[attr-defined]


def _triple_for_request(
    request: str,
    host_triple: str,
    system_request: str | None = None,
) -> str:
    if request == 'auto':
        if str(system_request or '').strip().lower() != 'baremetal':
            return host_triple
        request = host_triple.split('-', 1)[0]

    if '-' in request:
        return request

    architecture = _ARCH_ALIASES.get(request)
    if architecture is None:
        raise TargetResolutionError(
            f"Target Arch invalido: {request!r}. Use 'auto', 'x86', 'amd', "
            "'arm', 'riscv32', 'riscv64' o un triple LLVM."
        )

    if str(system_request or '').strip().lower() == 'baremetal':
        return f'{architecture}-unknown-none-elf'

    parts = host_triple.split('-')
    parts[0] = architecture
    return '-'.join(parts)


def resolve_target(
    request: str | None = None,
    system_request: str | None = None,
) -> TargetHandle:
    initialize_llvm()
    normalized = str(request or 'auto').strip().lower()
    host_triple = llvm.get_default_triple()
    triple = _triple_for_request(normalized, host_triple, system_request)

    try:
        target = llvm.Target.from_triple(triple)
        machine = target.create_target_machine(codemodel='small')
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
