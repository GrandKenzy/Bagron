import sys
from pathlib import Path

from core import frontend
from core.compiler.prep import extract_prep_blocks
from core.frontend.aot import AotParser, AotParserError
from tools.diagnostic import Diagnostics


class CompilationError(RuntimeError):
    pass


class CompilerState(Diagnostics):
    def __init__(self):
        self.semantic_errors: list[str] = []
        self.warnings: list[str] = []
        self.function_bindings: dict[int, object] = {}
        self.type_bindings: dict[int, object] = {}
        self._aot_parser: AotParser | None = None
        self._aot_config_checked = False
        self._aot_config_error: AotParserError | None = None
        super().__init__('Compiler', 'Compiler', 'Diagnostics for compiler', True, True, True)

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
    for p in source.iterdir():
        if p.is_dir():
            continue
        if p.name in ('main.bg', '_main.bg'):
            return p
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
