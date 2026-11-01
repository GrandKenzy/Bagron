import sys
from pathlib import Path

from core import frontend
from core.compiler.prep import extract_prep_blocks
from core.frontend.aot import AotParser, AotParserError
from tools.diagnostic import Diagnostics


class CompilationError(RuntimeError):
    pass


class CompilerState(Diagnostics):
    def __init__(
        self,
        *,
        aot: bool | None = None,
        aot_parser: str | Path | None = None,
        aot_strict: bool = False,
    ):
        self.semantic_errors: list[str] = []
        self.warnings: list[str] = []
        self.function_bindings: dict[int, object] = {}
        self.type_bindings: dict[int, object] = {}
        # `None` es el modo auto: usa GIR si el parser construido está
        # disponible y conserva Python cuando el checkout no tiene Clang/AOT.
        self.aot_requested = aot
        self.aot_parser_path = aot_parser
        self.aot_strict = aot_strict
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

    def exit(self):  # NOTE: Función temporal en lo que armamos los errores
        print(self.last_note())
        sys.exit(1)

    def _get_aot_parser(self) -> AotParser:
        if self._aot_parser is not None:
            return self._aot_parser
        if self._aot_config_checked and self._aot_config_error is not None:
            raise self._aot_config_error

        self._aot_config_checked = True
        try:
            self._aot_parser = AotParser.from_config(self.aot_parser_path)
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
            if self.aot_requested is not False:
                try:
                    parser = self._get_aot_parser()
                    return parser.parse(
                        content,
                        session=frontend.BAGRON_SESSION,
                        name=path.name,
                    )
                except AotParserError as error:
                    if self.aot_strict:
                        raise CompilationError(str(error)) from error
                    if self.aot_requested is True or self._aot_parser is not None:
                        self.warning(
                            f'AOT no disponible para {path.name}; se usara Gram Python: {error}'
                        )

            # Session.tokenize/parse ya usan el estado aislado de Gram; no
            # reactives el catálogo global legacy antes de cada compilación.
            TKNS = frontend.BAGRON_SESSION.tokenize(content, path.name)
            return frontend.BAGRON_SESSION.parse(TKNS, path.name, trace='off')
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
