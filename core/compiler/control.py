import sys
from pathlib import Path

from core import frontend
from core.compiler.links import extract_link_directives
from core.library import extract_library_directives
from core.compiler.prep import extract_prep_blocks, preprocess_conditionals
from core.frontend.aot import AotParser, AotParserError
from tools.diagnostic import Diagnostics


class CompilationError(RuntimeError):
    pass


class CompilerState(Diagnostics):
    def __init__(self):
        self.semantic_errors: list[str] = []
        self.warnings: list[str] = []
        # Con --strict-ownership las fugas de buffers y descriptores son error.
        self.strict_ownership = False
        self.function_bindings: dict[int, object] = {}
        self.type_bindings: dict[int, object] = {}
        self._aot_parser: AotParser | None = None
        self._aot_config_checked = False
        self._aot_config_error: AotParserError | None = None
        # Los diagnósticos permanecen en memoria; no generar logs por defecto.
        super().__init__('Compiler', 'Compiler', 'Diagnostics for compiler', True, False, False)

    def error(self, note: str):
        self.semantic_errors.append(note)
        super().error(note)

    def warning(self, note: str):
        """Register a non-fatal compiler warning in diagnostics and state."""
        self.warnings.append(note)
        super().warn(note)

    def exit(self):
        print(self.last_note())
        sys.exit(1)

    def _get_aot_parser(self) -> AotParser:
        if self._aot_parser is not None:
            return self._aot_parser
        if self._aot_config_checked and self._aot_config_error is not None:
            raise self._aot_config_error

        self._aot_config_checked = True
        try:
            self._aot_parser = AotParser.from_config()
        except AotParserError as error:
            self._aot_config_error = error
            raise
        return self._aot_parser

    def process_source(self, path: Path):
        ext = path.suffix

        content = _open_file(self, path)

        # Process conditionals before extracting library directives so a
        # platform-specific dependency can be guarded by ``#if OS``.  The
        # target is already selected from the entry module before this method
        # runs, and the preprocessor preserves source line positions.
        content, conditional_errors = preprocess_conditionals(
            content,
            Path(path),
            system=getattr(self, 'preprocessor_system', 'auto'),
            architecture=getattr(self, 'preprocessor_architecture', 'auto'),
        )
        for error in conditional_errors:
            self.error(error)

        content, library_requests, library_errors = extract_library_directives(
            content,
            Path(path),
            allow=(
                Path(path).resolve() == getattr(self, 'main_module_path', None)
                or any(
                    Path(path).resolve().is_relative_to(root)
                    for root in getattr(self, 'library_source_roots', ())
                )
            ),
        )
        if hasattr(self, 'library_requests') and library_requests:
            self.library_requests.setdefault(Path(path).resolve(), []).extend(
                library_requests
            )
        for error in library_errors:
            self.error(error)

        content, link_directories, link_errors = extract_link_directives(
            content,
            Path(path),
            project_root=getattr(self, 'project_root', Path(path).parent),
            allow=Path(path).resolve() == getattr(self, 'main_module_path', None),
        )
        if hasattr(self, 'storage'):
            for directory in link_directories:
                if directory not in self.storage.native_link_dirs:
                    self.storage.native_link_dirs.append(directory)
        for error in link_errors:
            self.error(error)

        content, prep_blocks, prep_errors = extract_prep_blocks(content, Path(path))
        if hasattr(self, 'prep_blocks'):
            self.prep_blocks.extend(prep_blocks)
        for error in prep_errors:
            self.error(error)

        ext = ext.strip('.')
        if ext == 'bg':
            try:
                parser = self._get_aot_parser()
                return parser.parse(
                    content,
                    session=frontend.BAGRON_SESSION,
                    name=str(path),
                )
            except AotParserError as error:
                raise CompilationError(
                    f'El frontend FFI de Gram no pudo producir GIR para {path}: {error}'
                ) from error
        else:
            self.error(f'La extensión {ext} no está soportada.')
            self.exit()


def _found_main(source: Path):
    for root in (source, source / 'modules'):
        if not root.is_dir():
            continue
        for name in ('main.bg', '_main.bg'):
            candidate = root / name
            if candidate.is_file():
                return candidate
    return None


def _open_file(cdiag: CompilerState, source: str | Path):
    if isinstance(source, str):
        source = Path(source)

    if not source.exists():
        cdiag.error(f'El archivo especificado no existe: {source}')
        cdiag.exit()

    try:
        content = source.read_text(encoding='utf-8')
    except PermissionError as e:
        cdiag.fatal(f'No se pudo abrir {source}. Permiso denegado: {e}')
        cdiag.exit()

    return content.splitlines(keepends=True)
