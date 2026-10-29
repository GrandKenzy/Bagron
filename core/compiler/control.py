import sys
from pathlib import Path

from core import frontend
from core.compiler.prep import extract_prep_blocks
from tools.diagnostic import Diagnostics


class CompilationError(RuntimeError):
    pass


class CompilerState(Diagnostics):
    def __init__(self):
        self.semantic_errors: list[str] = []
        self.function_bindings: dict[int, object] = {}
        self.type_bindings: dict[int, object] = {}
        super().__init__('Compiler', 'Compiler', 'Diagnostics for compiler', True, True, True)

    def error(self, note: str):
        self.semantic_errors.append(note)
        super().error(note)

    def exit(self):  # NOTE: Función temporal en lo que armamos los errores
        print(self.last_note())
        sys.exit(1)

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
            frontend.BAGRON_SESSION.load()
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
