from dataclasses import dataclass, replace
from pathlib import Path
import re

from core import globvars, storage
from core.compiler.control import CompilationError, CompilerState, _found_main
from core.compiler.platforms import (
    architecture_name,
    detect_host_platform,
    detect_host_system,
    normalize_architecture,
    normalize_system,
    validate_architecture_option,
    validate_system_option,
)
from core.compiler.prep import (
    PrepBlock,
    PrepError,
    preprocess_conditionals,
    write_prep_files,
)
from core.frontend import processor as bagron_processor
from core.library import (
    LibraryError,
    extract_library,
    extract_library_directives,
    _node_from_data,
    resolve_library_path,
)
from core.compiler.mangling import MANGLE_VERSION, symbol_llvm_name
from core.frontend.objects import (
    AggregateSymbol,
    EnumSymbol,
    FunctionSignature,
    FunctionSymbol,
    OpaqueSymbol,
    ParameterSpec,
    TypeSpec,
    ValueInfo,
    Variable,
)


@dataclass(frozen=True)
class ModuleTarget:
    """Target and ABI clauses declared by one source module.

    ``None`` is intentional: an omitted dimension inherits the target selected
    by the project entry module and does not declare a separate constraint.
    """

    system: str | None = None
    architecture: str | None = None
    boot: str | None = None
    abi: str | None = None


class Compiler(CompilerState):
    def __init__(self):
        super().__init__()
        self.storage = storage.Storage('main')
        self.function_lookup = storage.FunctionLookup(self.storage)
        self.project_root: Path | None = None
        self._loaded_module_paths: set[Path] = set()
        self._loading_module_paths: list[Path] = []
        self.import_requests = []
        self.library_requests: dict[Path, list[object]] = {}
        self.library_source_roots: set[Path] = set()
        self.library_targets: dict[Path, Path] = {}
        self.module_package_ids: dict[Path, str] = {}
        self.module_package_relatives: dict[Path, str] = {}
        self.library_symbol_names: dict[tuple[str, str, str, str], str] = {}
        self.library_module_paths: dict[Path, set[Path]] = {}
        self.package_identity_override: str | None = None
        self.precompiled_modules: dict[Path, list[object]] = {}
        self.module_exports: dict[Path, set[str]] = {}
        self.module_targets: dict[Path, ModuleTarget] = {}
        self.node_modules: dict[int, Path] = {}
        self.active_module_path: Path | None = None
        self.main_module_path: Path | None = None
        self.prep_blocks: list[PrepBlock] = []
        self.preprocessor_system = self._normalize_target_system(None)
        self.preprocessor_architecture = self._normalize_target_architecture(None)

    def module_for_node(self, node: object) -> Path | None:
        return self.node_modules.get(id(node), self.active_module_path)

    def activate_module(self, path: Path | None) -> None:
        """Set the module context used by flattened semantic lookups."""
        self.active_module_path = path.resolve() if path is not None else None
        self.storage.active_module_path = self.active_module_path

    @staticmethod
    def _node_token_value(node: object) -> object | None:
        token = getattr(node, 'token', None)
        return getattr(token, 'value', None)

    def _register_module_target(self, path: Path, nodes: list[object]) -> None:
        """Record target clauses before any flattened semantic pass runs."""
        values: dict[str, str] = {}
        seen: set[str] = set()
        for node in nodes:
            if getattr(node, 'name', None) != 'CLAUSE':
                continue
            children = getattr(node, 'nodes', ())
            if len(children) < 3:
                continue
            clause_name = self._node_token_value(children[1])
            clause_value = self._node_token_value(children[2])
            if clause_name not in ('System', 'Arch', 'Boot', 'ABI'):
                continue
            if clause_name in seen:
                self.error(
                    f'El modulo {path} declara la clausula {clause_name!r} mas de una vez'
                )
                continue
            seen.add(clause_name)
            values[clause_name] = str(clause_value)

        self.module_targets[path] = ModuleTarget(
            system=values.get('System'),
            architecture=values.get('Arch'),
            boot=values.get('Boot'),
            abi=values.get('ABI'),
        )

    @staticmethod
    def _normalize_target_system(value: str | None) -> str:
        if value is None or str(value).strip().lower() == 'auto':
            return detect_host_system()
        return normalize_system(value)

    @staticmethod
    def _read_source_target_clauses(path: Path) -> dict[str, str]:
        """Read target clauses needed before the source can be parsed."""
        clause_re = re.compile(
            r'^\s*clause\s+(?P<name>System|Arch|Boot|ABI)\s+'
            r'(?P<quote>["\'])(?P<value>.*?)\2\s*$'
        )
        raw_lines = path.read_text(encoding='utf-8').splitlines(keepends=True)
        host = detect_host_platform()
        selected_lines, _ = preprocess_conditionals(
            raw_lines,
            path,
            system=host.system,
            architecture=host.architecture,
        )
        values: dict[str, str] = {}
        for line in selected_lines:
            match = clause_re.match(line)
            if match is not None and match.group('name') not in values:
                values[match.group('name')] = match.group('value')
        return values

    @staticmethod
    def _host_architecture() -> str:
        return detect_host_platform().architecture

    @classmethod
    def _normalize_target_architecture(cls, value: str | None) -> str:
        raw = cls._host_architecture() if value is None else value
        return architecture_name(normalize_architecture(raw))

    @classmethod
    def _target_architecture_identity(
        cls,
        value: str | None,
        system_name: str,
    ) -> str:
        """Keep Android API levels when comparing imported module targets."""
        raw = None if value is None or str(value).strip().lower() == 'auto' else value
        if system_name == 'android' and raw is not None:
            return normalize_architecture(raw)
        return cls._normalize_target_architecture(raw)

    @staticmethod
    def _normalize_boot(value: str | None) -> str:
        return str(value or 'none').strip().lower()

    @staticmethod
    def _triple_environment(value: str | None) -> set[str]:
        """Return recognizable OS/environment components from an LLVM triple."""
        if not value or '-' not in value:
            return set()
        parts = [part.lower() for part in str(value).split('-')[1:]]
        known = {
            'linux', 'gnu', 'musl', 'windows', 'win32', 'mingw', 'msvc',
            'android', 'darwin', 'macos', 'ios', 'none', 'elf', 'uefi',
        }
        environment = {part for part in parts if part in known}
        if any(part.startswith('android') for part in parts):
            environment.add('android')
        return environment

    @classmethod
    def _validate_target_configuration(
        cls,
        path: Path,
        system_name: str,
        architecture: str,
        boot: str,
        raw_architecture: str | None,
    ) -> None:
        """Reject target combinations that cannot describe one platform."""
        try:
            validate_system_option(system_name)
            validate_architecture_option(raw_architecture or architecture)
        except ValueError as error:
            raise ValueError(str(error)) from error

        if system_name in {'darwin', 'macos'}:
            raise ValueError(
                f'El modulo {path} declara System {system_name!r}; '
                'Bagron AOT solo soporta Windows, Linux y Android actualmente'
            )
        if system_name == 'android':
            if raw_architecture is None:
                raise ValueError(
                    f'El modulo {path} debe declarar Arch con un triple Android '
                    'explicito, por ejemplo "aarch64-linux-android35"'
                )
            from core.backend.llvm.android_toolchain import (
                AndroidToolchainError,
                parse_android_target,
            )

            try:
                parse_android_target(raw_architecture)
            except AndroidToolchainError as error:
                raise ValueError(
                    f'El modulo {path} declara un target Android invalido: {error}'
                ) from error
        if system_name != 'baremetal' and boot != 'none':
            cls_error = (
                f'El modulo {path} declara Boot {boot!r}, pero System '
                f'{system_name!r} no admite un protocolo de arranque bare-metal'
            )
            raise ValueError(cls_error)

        if system_name == 'baremetal':
            if boot == 'multiboot2' and architecture not in {'i386', 'x86_64'}:
                raise ValueError(
                    f'El modulo {path} declara Boot "multiboot2" para Arch '
                    f'{architecture!r}; esta implementación solo soporta '
                    'x86/i386 y x86-64'
                )
            if boot == 'uefi' and architecture not in {'i386', 'x86_64', 'aarch64'}:
                raise ValueError(
                    f'El modulo {path} declara Boot "uefi" para Arch '
                    f'{architecture!r}; usa x86, amd o arm64'
                )
            if boot == 'opensbi' and not architecture.startswith('riscv'):
                raise ValueError(
                    f'El modulo {path} declara Boot "opensbi" para Arch '
                    f'{architecture!r}; OpenSBI requiere RISC-V'
                )

        environment = cls._triple_environment(raw_architecture)
        if 'android' in environment and system_name != 'android':
            raise ValueError(
                f'El modulo {path} declara el triple Android '
                f'{raw_architecture!r}; Android es reconocido, pero debe usar '
                'System "android"'
            )
        if system_name == 'baremetal' and environment & {
            'linux', 'gnu', 'musl', 'windows', 'win32', 'mingw', 'msvc',
            'darwin', 'macos', 'ios',
        }:
            raise ValueError(
                f'El modulo {path} combina System "baremetal" con un triple '
                f'con sistema operativo: {raw_architecture!r}'
            )
        if system_name == 'windows' and environment & {'linux', 'none', 'elf'}:
            raise ValueError(
                f'El modulo {path} combina System "windows" con el triple '
                f'{raw_architecture!r}'
            )
        if system_name == 'linux' and environment & {'windows', 'win32', 'msvc', 'none'}:
            raise ValueError(
                f'El modulo {path} combina System "linux" con el triple '
                f'{raw_architecture!r}'
            )

    def _validate_module_targets(self) -> None:
        """Validate every loaded module against the entry module target.

        The entry module selects the compilation target. Imported modules use
        that target for every omitted dimension. Explicit clauses remain local
        declarations and must be compatible with the entry target.
        """
        main_path = self.main_module_path
        if main_path is None:
            return

        main_target = self.module_targets.get(main_path, ModuleTarget())
        target_system = self._normalize_target_system(main_target.system)
        target_architecture = self._normalize_target_architecture(
            main_target.architecture
        )
        target_architecture_identity = self._target_architecture_identity(
            main_target.architecture,
            target_system,
        )
        target_boot = self._normalize_boot(main_target.boot)
        target_abi = (
            str(main_target.abi).strip().lower()
            if main_target.abi is not None
            else None
        )

        if target_abi is not None and target_abi != 'sysv_amd64':
            self.error(
                f'El ABI {main_target.abi!r} no esta soportada; '
                'usa "sysv_amd64"'
            )
        if target_system == 'baremetal':
            if main_target.abi is None:
                self.error(
                    'El target baremetal requiere una clausula ABI explicita; '
                    'usa "sysv_amd64"'
                )
            elif target_abi != 'sysv_amd64':
                self.error(
                    'El target baremetal AMD64 requiere la ABI "sysv_amd64"'
                )
            if target_abi == 'sysv_amd64' and target_architecture != 'x86_64':
                self.error(
                    'La ABI "sysv_amd64" solo esta disponible para arquitectura '
                    f'AMD64, no para {target_architecture!r}'
                )
        elif main_target.abi is not None:
            self.error(
                'La clausula ABI solo se permite con System "baremetal"'
            )

        if target_system == 'baremetal' and main_target.boot is None:
            self.error(
                'El target baremetal requiere una clausula Boot explicita; '
                'usa "none", "multiboot2", "uefi", "opensbi", "dtb" o "custom"'
            )
        try:
            self._validate_target_configuration(
                main_path,
                target_system,
                target_architecture,
                target_boot,
                main_target.architecture,
            )
        except ValueError as error:
            self.error(str(error))

        for path, module_target in self.module_targets.items():
            if path != main_path and module_target.abi is not None:
                module_abi = str(module_target.abi).strip().lower()
                if target_system != 'baremetal':
                    self.error(
                        f'El modulo {path} declara ABI {module_target.abi!r}, '
                        'pero la clausula ABI solo se permite con System '
                        '"baremetal"'
                    )
                elif module_abi != target_abi:
                    self.error(
                        f'El modulo {path} declara ABI {module_target.abi!r}, '
                        f'incompatible con la ABI del proyecto {target_abi!r}'
                    )

            if (
                module_target.system is not None
                and self._normalize_target_system(module_target.system)
                != target_system
            ):
                self.error(
                    f'El modulo {path} declara System '
                    f'{module_target.system!r}, incompatible con el target del proyecto '
                    f'{target_system!r}'
                )

            if (
                module_target.architecture is not None
                and self._target_architecture_identity(
                    module_target.architecture,
                    target_system,
                )
                != target_architecture_identity
            ):
                self.error(
                    f'El modulo {path} declara Arch '
                    f'{module_target.architecture!r}, incompatible con el target del proyecto '
                    f'{target_architecture!r}'
                )

            if (
                module_target.boot is not None
                and self._normalize_boot(module_target.boot) != target_boot
            ):
                self.error(
                    f'El modulo {path} declara Boot '
                    f'{module_target.boot!r}, incompatible con el target del '
                    f'proyecto {target_boot!r}'
                )

            if (
                module_target.system is not None
                or module_target.architecture is not None
                or module_target.boot is not None
            ):
                # An omitted dimension inherits the entry target, so validate
                # partial declarations against the effective target instead of
                # falling back to the host target.
                module_system = (
                    target_system
                    if module_target.system is None
                    else self._normalize_target_system(module_target.system)
                )
                module_architecture = (
                    target_architecture
                    if module_target.architecture is None
                    else self._normalize_target_architecture(
                        module_target.architecture
                    )
                )
                module_boot = (
                    target_boot
                    if module_target.boot is None
                    else self._normalize_boot(module_target.boot)
                )
                try:
                    self._validate_target_configuration(
                        path,
                        module_system,
                        module_architecture,
                        module_boot,
                        module_target.architecture or main_target.architecture,
                    )
                except ValueError as error:
                    self.error(str(error))

    def _load_module_tree(self, path: Path):
        path = path.resolve()
        precompiled = self.precompiled_modules.get(path)
        if precompiled is not None:
            return self._load_precompiled_module_tree(path, precompiled)
        if path in self._loading_module_paths:
            cycle = ' -> '.join(
                str(item) for item in (*self._loading_module_paths, path)
            )
            self.error(f'Ciclo de importacion detectado: {cycle}')
            return []
        if path in self._loaded_module_paths:
            return []
        if path.suffix != '.bg':
            self.error(f'El modulo importado no es un archivo .bg: {path}')
            return []
        if not path.is_file():
            self.error(f'El modulo Bagron no existe: {path}')
            return []

        from core.frontend.tools import imports

        self._loading_module_paths.append(path)
        try:
            nodes = self.process_source(path)
            for node in nodes:
                self.node_modules[id(node)] = path
            self._register_module_target(path, nodes)
            ordered = []
            for request in self.library_requests.get(path, ()):
                ordered.extend(self._load_library(request))
            for node in nodes:
                if node.name != 'IMPORT':
                    continue
                name = imports.module_name(node)
                if name is None:
                    self.error(
                        f'La declaracion import no contiene un modulo valido: '
                        f'{path}'
                    )
                    continue
                imported_path = imports.resolve_module_path(self, name, path)
                if imported_path is not None:
                    request = imports.parse_request(
                        node,
                        target=imported_path,
                        source=path,
                    )
                    if request is not None:
                        self.import_requests.append(request)
                    ordered.extend(self._load_module_tree(imported_path))

            own_nodes = [node for node in nodes if node.name != 'IMPORT']
            self.module_exports[path] = imports.public_definition_names(own_nodes)
            self._loaded_module_paths.add(path)
            self.storage.loaded_modules.append(str(path))
            return ordered + own_nodes
        finally:
            self._loading_module_paths.pop()

    def _load_precompiled_module_tree(self, path: Path, nodes: list[object]):
        """Load a validated lib1 frontend module without parsing its source."""
        from core.frontend.tools import imports

        if path in self._loading_module_paths:
            cycle = ' -> '.join(
                str(item) for item in (*self._loading_module_paths, path)
            )
            self.error(f'Ciclo de importacion detectado: {cycle}')
            return []
        if path in self._loaded_module_paths:
            return []

        self._loading_module_paths.append(path)
        try:
            for node in nodes:
                self.node_modules[id(node)] = path
            self._register_module_target(path, nodes)
            ordered: list[object] = []
            for node in nodes:
                if getattr(node, 'name', None) != 'IMPORT':
                    continue
                name = imports.module_name(node)
                if name is None:
                    self.error(
                        f'La declaracion import no contiene un modulo valido: {path}'
                    )
                    continue
                imported_path = imports.resolve_module_path(self, name, path)
                if imported_path is not None:
                    request = imports.parse_request(
                        node,
                        target=imported_path,
                        source=path,
                    )
                    if request is not None:
                        self.import_requests.append(request)
                    ordered.extend(self._load_module_tree(imported_path))

            own_nodes = [node for node in nodes if getattr(node, 'name', None) != 'IMPORT']
            self.module_exports[path] = imports.public_definition_names(own_nodes)
            self._loaded_module_paths.add(path)
            self.storage.loaded_modules.append(str(path))
            return ordered + own_nodes
        finally:
            self._loading_module_paths.pop()

    def _load_library(self, request):
        """Load a lib1 package and bind its public export namespace."""
        from core.frontend.tools.imports import ImportRequest
        from core.compiler.prep import PrepBlock

        source = Path(request.source).resolve()
        package_path = resolve_library_path(
            request.path,
            source,
            self.project_root or source.parent,
            global_name=request.global_name,
        )
        if package_path is None:
            self.error(
                f'No se encontro la libreria Bagron {request.path!r} desde {source}'
            )
            return []

        cache_root = (
            (self.project_root or source.parent) / 'build' / '.bagron' / 'libraries'
        )
        try:
            package, extracted = extract_library(package_path, cache_root)
        except LibraryError as error:
            self.error(str(error))
            return []
        if package.library_version == 2:
            self._load_compiled_library(package, extracted, request)
            return []

        synthetic = self.library_targets.get(package_path)
        ordered: list[object] = []
        if synthetic is None:
            synthetic = extracted / '__lib1__.bg'
            self.library_targets[package_path] = synthetic
            source_root = extracted / 'source'
            self.library_source_roots.add(source_root.resolve())
            for relative in package.modules:
                module_path = (extracted / relative).resolve()
                self.module_package_ids[module_path] = package.package_id
                self.module_package_relatives[module_path] = str(
                    Path(relative).relative_to('source').as_posix()
                )
                self.library_module_paths.setdefault(synthetic, set()).add(module_path)
            for item in package.symbols.get('exports', ()):
                if not isinstance(item, dict):
                    continue
                name = str(item.get('name', ''))
                module = str(item.get('module', ''))
                kind = str(item.get('kind', ''))
                llvm_name = item.get('llvm') or item.get('mangled')
                if module.startswith(('build/', '.bagron/')):
                    continue
                if name and module and llvm_name:
                    self.library_symbol_names[
                        (package.package_id, module, kind, name)
                    ] = str(llvm_name)
            for relative in package.manifest.get('links', ()):
                link_dir = (extracted / str(relative)).resolve()
                try:
                    link_dir.relative_to(extracted.resolve())
                except ValueError:
                    self.error(
                        f'El #link de {package_path} sale de la raiz del paquete: '
                        f'{relative!r}'
                    )
                    continue
                if link_dir.is_dir() and link_dir not in self.storage.native_link_dirs:
                    self.storage.native_link_dirs.append(link_dir)
            for native_dir in (extracted / 'bins', extracted / 'libs'):
                if native_dir.is_dir() and native_dir.resolve() not in self.storage.native_link_dirs:
                    self.storage.native_link_dirs.append(native_dir.resolve())
            for module in package.ir.get('modules', ()):
                if not isinstance(module, dict):
                    self.error(f'La IR de {package_path} contiene un modulo invalido')
                    continue
                relative = str(module.get('path', ''))
                module_path = (
                    extracted / relative
                    if relative.startswith('source/')
                    else source_root / relative
                ).resolve()
                try:
                    module_path.relative_to(source_root.resolve())
                except ValueError:
                    self.error(
                        f'El modulo IR {relative!r} sale de source/ en {package_path}'
                    )
                    continue
                try:
                    module_nodes = [
                        _node_from_data(item) for item in module.get('nodes', ())
                    ]
                except (KeyError, TypeError, ValueError) as error:
                    self.error(
                        f'No se pudo cargar la IR del modulo {relative!r}: {error}'
                    )
                    continue
                self.precompiled_modules[module_path] = module_nodes
                # Los bloques ASM se serializan fuera de los nodos GIR; deben
                # volver al estado del compilador para generar el objeto nativo
                # junto con el resto del programa consumidor.
                for item in module.get('prep_blocks', ()):
                    if not isinstance(item, dict):
                        self.error(
                            f'La IR de {package_path} contiene un bloque ASM invalido'
                        )
                        continue
                    self.prep_blocks.append(PrepBlock(
                        source=module_path,
                        function_name=item.get('function_name'),
                        dialect=str(item.get('dialect', '')),
                        body=str(item.get('body', '')),
                        line=int(item.get('line', 1)),
                    ))
            main_path = next(
                (
                    source_root / candidate
                    for candidate in ('main.bg', '_main.bg')
                    if (source_root / candidate).is_file()
                ),
                None,
            )
            if main_path is not None:
                source_lines = main_path.read_text(encoding='utf-8').splitlines(keepends=True)
                selected_lines, cond_errors = preprocess_conditionals(
                    source_lines,
                    main_path,
                    system=self.preprocessor_system,
                    architecture=self.preprocessor_architecture,
                )
                for err in cond_errors:
                    self.error(err)
                _, dep_requests, dep_errors = extract_library_directives(
                    selected_lines,
                    main_path,
                    allow=True,
                )
                for err in dep_errors:
                    self.error(err)
                for dep_request in dep_requests:
                    ordered.extend(self._load_library(dep_request))

            for relative in package.modules:
                module_path = (extracted / relative).resolve()
                try:
                    module_path.relative_to(source_root.resolve())
                except ValueError:
                    self.error(
                        f'El modulo {relative!r} de {package_path} esta fuera de source/'
                    )
                    continue
                if not module_path.is_file():
                    self.error(
                        f'Falta el modulo {relative!r} dentro de {package_path}'
                    )
                    continue
                ordered.extend(self._load_module_tree(module_path))

            exports = {
                str(item.get('name'))
                for item in package.symbols.get('exports', ())
                if isinstance(item, dict)
                and item.get('name')
                and not str(item.get('module', '')).startswith(('build/', '.bagron/'))
            }
            self.module_exports[synthetic] = exports
            targets = package.targets
            self.module_targets[synthetic] = ModuleTarget(
                system=targets.get('System'),
                architecture=targets.get('Arch'),
                boot=targets.get('Boot'),
                abi=targets.get('ABI'),
            )
            self._loaded_module_paths.add(synthetic)
            self.storage.loaded_modules.append(str(package_path))

        self.import_requests.append(ImportRequest(
            package.name,
            alias=request.alias,
            target=synthetic,
            source=source,
        ))
        return ordered

    @staticmethod
    def _library_type_spec(data: object) -> TypeSpec:
        values = data if isinstance(data, dict) else {}
        return TypeSpec(
            name=str(values.get('name', 'void')),
            bit_width=values.get('bit_width'),
            signed=values.get('signed'),
            pointer_level=int(values.get('pointer_level', 0)),
            array_depth=int(values.get('array_depth', 0)),
            value_is_const=bool(values.get('value_is_const', False)),
            pointer_is_const=bool(values.get('pointer_is_const', False)),
            array_lengths=tuple(values.get('array_lengths', ()) or ()),
        )

    @classmethod
    def _library_signature(cls, data: object) -> FunctionSignature:
        values = data if isinstance(data, dict) else {}
        parameters = []
        for item in values.get('parameters', ()):
            if not isinstance(item, dict):
                continue
            parameters.append(ParameterSpec(
                name=str(item.get('name', 'arg')),
                type_spec=cls._library_type_spec(item.get('type', {})),
                is_length=bool(item.get('is_length', False)),
                is_size=bool(item.get('is_size', False)),
                is_signed=bool(item.get('is_signed', False)),
                is_region=bool(item.get('is_region', False)),
                is_receiver=bool(item.get('is_receiver', False)),
                is_unique=bool(item.get('is_unique', False)),
                length_of=item.get('length_of'),
                signed_of=item.get('signed_of'),
                region_of=item.get('region_of'),
            ))
        return FunctionSignature(
            parameters=tuple(parameters),
            return_type=cls._library_type_spec(values.get('return', {})),
        )

    def _load_compiled_library(self, package, extracted: Path, request) -> None:
        """Load lib2 declarations and native artifacts into the final link."""
        from core.frontend.tools.imports import ImportRequest

        synthetic = self.library_targets.get(package.path)
        if synthetic is None:
            synthetic = extracted / '__lib2__.bg'
            self.library_targets[package.path] = synthetic
            source_root = extracted / 'source'
            module_paths: set[Path] = set()
            for item in package.symbols.get('exports', ()):
                if not isinstance(item, dict):
                    continue
                module = str(item.get('module', ''))
                if not module:
                    continue
                module_path = (source_root / module).resolve()
                module_paths.add(module_path)
                self.module_package_ids[module_path] = package.package_id
                self.module_package_relatives[module_path] = module
                name = str(item.get('name', ''))
                kind = str(item.get('kind', ''))
                llvm_name = item.get('llvm')
                if name and llvm_name:
                    self.library_symbol_names[
                        (package.package_id, module, kind, name)
                    ] = str(llvm_name)
            self.library_module_paths[synthetic] = module_paths

            for native_dir in (extracted / 'bins', extracted / 'libs'):
                if native_dir.is_dir() and native_dir.resolve() not in self.storage.native_link_dirs:
                    self.storage.native_link_dirs.append(native_dir.resolve())
            for link in package.manifest.get('native_links', ()):
                if str(link) not in self.storage.native_links:
                    self.storage.native_links.append(str(link))
            artifact_name = str(package.artifacts.get('object', ''))
            artifact_path = (extracted / artifact_name).resolve()
            try:
                artifact_path.relative_to(extracted.resolve())
            except ValueError as error:
                self.error(f'El objeto de la lib2 escapa del paquete: {artifact_name!r}')
            else:
                if not artifact_path.is_file():
                    self.error(f'Falta el objeto de la lib2: {artifact_name!r}')
                elif artifact_path not in self.storage.native_objects:
                    self.storage.native_objects.append(artifact_path)

            exports = {
                str(item.get('name'))
                for item in package.symbols.get('exports', ())
                if isinstance(item, dict) and item.get('name')
            }
            self.module_exports[synthetic] = exports
            targets = package.targets
            self.module_targets[synthetic] = ModuleTarget(
                system=targets.get('System'),
                architecture=targets.get('Arch'),
                boot=targets.get('Boot'),
                abi=targets.get('ABI'),
            )
            for item in package.symbols.get('exports', ()):
                if not isinstance(item, dict):
                    continue
                name = str(item.get('name', ''))
                module = str(item.get('module', ''))
                module_path = (extracted / 'source' / module).resolve()
                kind = str(item.get('kind', ''))
                if not name or not module:
                    continue
                if kind in {'function', 'method'}:
                    symbol_name = name
                    owner = None
                    if kind == 'method':
                        owner = str(item.get('owner', '')) or None
                        symbol_name = f'{owner}__{name}' if owner else name
                    symbol = FunctionSymbol(
                        symbol_name,
                        self._library_signature(item.get('signature', {})),
                        decorators=tuple(item.get('decorators', ()) or ()),
                        is_inline=bool(item.get('is_inline', False)),
                        owner_type=owner,
                        source_name=name,
                        is_method=kind == 'method',
                        is_static=bool(item.get('is_static', False)),
                        module_path=module_path,
                        privacy='public',
                        is_compiled=True,
                    )
                    symbol.llvm_name = str(item.get('llvm') or symbol_name)
                    registered = (
                        self.storage.define_method(symbol)
                        if kind == 'method'
                        else self.storage.define_function(symbol)
                    )
                    if not registered:
                        self.error(f'El simbolo lib2 ya existe: {name}')
                elif kind == 'opaque':
                    symbol = OpaqueSymbol(
                        name,
                        self._library_type_spec(item.get('representation', {})),
                        module_path=module_path,
                        llvm_name=str(item.get('llvm') or name),
                    )
                    if not self.storage.define_type(symbol):
                        self.error(f'El tipo lib2 ya existe: {name}')
                elif kind == 'variable':
                    type_spec = self._library_type_spec(item.get('type', {}))
                    value = item.get('value')
                    symbol = Variable(name, type_spec.name, type_spec.pointer_level, value)
                    symbol.type_spec = type_spec
                    symbol.value_is_const = bool(type_spec.value_is_const)
                    symbol.module_path = module_path
                    symbol.llvm_name = str(item.get('llvm') or name)
                    symbol.is_external = True
                    if value is not None:
                        symbol.value_info = ValueInfo(
                            type_spec,
                            is_literal=True,
                            value=value,
                        )
                    if not self.storage.add(name, symbol):
                        self.error(f'El global lib2 ya existe: {name}')

            self._loaded_module_paths.add(synthetic)
            self.storage.loaded_modules.append(str(package.path))

        self.import_requests.append(ImportRequest(
            package.name,
            alias=request.alias,
            target=synthetic,
            source=Path(request.source).resolve(),
        ))

    def compile(
        self,
        path: Path | str,
        executable: bool = True,
        *,
        require_main: bool = True,
    ):
        if isinstance(path, str):
            path = Path(path)

        if not path.exists():
            self.error(f'El source {path} no existe. Por favor, elija una ruta válida')
            self.exit()

        if path.is_dir():
            globvars.BASEDIR = path
            r = _found_main(path)
            if not r:
                self.error(f'No se encontró main.bg en {path}')
                self.exit()
            else:
                path = r

        path = path.resolve()
        globvars.BASEDIR = path.parent
        self.project_root = path.parent
        self.main_module_path = path
        declared_target = self._read_source_target_clauses(path)
        self.preprocessor_system = self._normalize_target_system(
            declared_target.get('System')
        )
        self.preprocessor_architecture = self._normalize_target_architecture(
            declared_target.get('Arch')
        )
        self._loaded_module_paths.clear()
        self._loading_module_paths.clear()
        self.import_requests.clear()
        self.library_requests.clear()
        self.library_source_roots.clear()
        self.library_targets.clear()
        self.precompiled_modules.clear()
        self.module_package_ids.clear()
        self.module_package_relatives.clear()
        self.library_symbol_names.clear()
        self.library_module_paths.clear()
        self.module_exports.clear()
        self.module_targets.clear()
        self.node_modules.clear()
        self.semantic_errors.clear()
        self.warnings.clear()
        self.activate_module(None)
        self.prep_blocks.clear()
        self.storage.prep_sources.clear()
        self.storage.prep_objects.clear()
        self.storage.prep_metadata.clear()
        self.storage.native_links.clear()
        self.storage.native_link_dirs.clear()
        self.storage.native_objects.clear()
        self.storage.root = str(path)

        AST = self._load_module_tree(path)

        self._validate_module_targets()
        if self.semantic_errors:
            raise CompilationError('\n'.join(self.semantic_errors))

        bagron_processor.process(self, AST)

        for block in self.prep_blocks:
            if block.function_name not in self.storage.functions:
                self.error(
                    f'El bloque ASM de {block.source}:{block.line} no pertenece '
                    f'a una funcion global emitible: {block.function_name}'
                )

        main = self.storage.functions.get('main')
        if require_main:
            if main is None:
                self.error('No se encontro la funcion global main')
            else:
                if main.signature.parameters:
                    self.error('La funcion global main no puede recibir parametros')
                if (
                    main.signature.return_type.name != 'int32'
                    or main.signature.return_type.pointer_level
                    or main.signature.return_type.array_depth
                ):
                    self.error('La funcion global main debe retornar int32')
                if 'main' in self.storage.namespace:
                    self.error('El nombre main no puede ser variable y funcion global a la vez')

        if self.semantic_errors:
            raise CompilationError('\n'.join(self.semantic_errors))

        self._assign_llvm_names()

        if self.prep_blocks:
            from core.backend.llvm.targets import TargetResolutionError, resolve_target

            try:
                target = resolve_target(
                    self.storage.architecture,
                    self.storage.system,
                    self.storage.optimizers,
                )
                prep_metadata = {}
                self.storage.prep_sources = write_prep_files(
                    self.prep_blocks,
                    self.project_root or path.parent,
                    functions=self.storage.functions,
                    target_triple=target.triple,
                    abi=self.storage.abi,
                    metadata=prep_metadata,
                )
                self.storage.prep_metadata = prep_metadata
            except (PrepError, TargetResolutionError) as error:
                raise CompilationError(str(error)) from error
        else:
            write_prep_files([], self.project_root or path.parent)

        from core.backend.llvm import LLVMBackend
        from core.backend.llvm.module import BackendError

        try:
            backend = LLVMBackend()
            if executable:
                return backend.build(self.storage)
            return backend.emit_module(self.storage)
        except BackendError as error:
            raise CompilationError(str(error)) from error

    def _symbol_identity(self, symbol: object) -> str:
        module_path = getattr(symbol, 'module_path', None)
        package_id = self.module_package_ids.get(
            Path(module_path).resolve() if module_path is not None else None
        )
        if package_id:
            return package_id
        if self.package_identity_override:
            return self.package_identity_override
        project = self.project_root.name if self.project_root is not None else 'project'
        return f'project:{project}'

    def _stored_llvm_name(self, symbol: object, kind: str) -> str | None:
        module_path = getattr(symbol, 'module_path', None)
        if module_path is None:
            return None
        resolved = Path(module_path).resolve()
        package_id = self.module_package_ids.get(resolved)
        if not package_id:
            return None
        module = self.module_package_relatives.get(resolved)
        if module is None:
            return None
        name = getattr(symbol, 'source_name', None) or getattr(symbol, 'name', None)
        if getattr(symbol, 'is_method', False):
            name = getattr(symbol, 'source_name', None) or name
        return self.library_symbol_names.get((package_id, module, kind, str(name)))

    @staticmethod
    def _patch_spec(spec: TypeSpec, target: object | None) -> TypeSpec:
        key = getattr(target, 'registry_key', None) if target is not None else None
        if key is None:
            return spec
        return replace(spec, nominal_key=key)

    def _patch_symbol_types(self, symbol: object) -> None:
        module_path = getattr(symbol, 'module_path', None)
        if module_path is not None:
            self.activate_module(Path(module_path))

        def resolve(spec: TypeSpec) -> TypeSpec:
            target = self.storage.resolve_type(spec.name)
            return self._patch_spec(spec, target)

        if isinstance(symbol, FunctionSymbol):
            parameters = tuple(
                replace(parameter, type_spec=resolve(parameter.type_spec))
                for parameter in symbol.signature.parameters
            )
            symbol.signature = FunctionSignature(
                parameters=parameters,
                return_type=resolve(symbol.signature.return_type),
            )
            for variable in symbol.local_variables.values():
                if getattr(variable, 'type_spec', None) is not None:
                    variable.type_spec = resolve(variable.type_spec)
            return
        if isinstance(symbol, Variable):
            if symbol.type_spec is not None:
                symbol.type_spec = resolve(symbol.type_spec)
            return
        if isinstance(symbol, OpaqueSymbol):
            symbol.representation = resolve(symbol.representation)
            return
        if isinstance(symbol, EnumSymbol):
            symbol.base_type = resolve(symbol.base_type)
            return
        if isinstance(symbol, AggregateSymbol):
            symbol.fields = tuple(
                replace(field, type_spec=resolve(field.type_spec))
                for field in symbol.fields
            )
            symbol.inherited_fields = tuple(
                replace(field, type_spec=resolve(field.type_spec))
                for field in symbol.inherited_fields
            )
            if symbol.base_type is not None:
                symbol.base_type = resolve(symbol.base_type)

    def _assign_llvm_names(self) -> None:
        """Assign backend identities once semantic validation is complete."""
        symbols: list[object] = []
        seen: set[int] = set()
        for value in (
            *self.storage.functions.values(),
            *self.storage.methods.values(),
            *self.storage.namespace.values(),
            *self.storage.types.values(),
        ):
            if id(value) in seen:
                continue
            seen.add(id(value))
            symbols.append(value)

        occupied: dict[str, object] = {}
        for symbol in symbols:
            identity = self._symbol_identity(symbol)
            symbol.package_id = (
                self.module_package_ids.get(Path(symbol.module_path).resolve())
                if getattr(symbol, 'module_path', None) is not None
                else None
            ) or (identity if identity != f'project:{self.project_root.name}' else None)
            if isinstance(symbol, FunctionSymbol):
                kind = 'method' if symbol.is_method else 'function'
            elif isinstance(symbol, Variable):
                kind = 'global'
            elif isinstance(symbol, EnumSymbol):
                kind = 'enum'
            elif isinstance(symbol, OpaqueSymbol):
                kind = 'opaque'
            else:
                kind = 'type'
            stored = self._stored_llvm_name(symbol, kind)
            symbol.llvm_name = stored or symbol_llvm_name(
                symbol,
                identity=identity,
                project_root=self.project_root,
            )
            if symbol.llvm_name in occupied and occupied[symbol.llvm_name] is not symbol:
                raise CompilationError(
                    f'Colision de nombre LLVM interno: {symbol.llvm_name}'
                )
            occupied[symbol.llvm_name] = symbol
            self._patch_symbol_types(symbol)
        self.activate_module(None)

    def resolve_import_symbol(self, target: Path, name: str, kind: str):
        """Resolve one export against the module requested by an import."""
        target = target.resolve()
        module_paths = self.library_module_paths.get(target, {target})
        if kind == 'function':
            candidates = self.storage.function_candidates.get(name, ())
        elif kind == 'variable':
            candidates = self.storage.variable_candidates.get(name, ())
        else:
            candidates = self.storage.type_candidates.get(name, ())
        for candidate in candidates:
            origin = getattr(candidate, 'module_path', None)
            if origin is not None and Path(origin).resolve() in module_paths:
                return candidate
        return None
