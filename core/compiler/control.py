import sys
from pathlib import Path

from core import frontend
from tools.diagnostic import Diagnostics


class CompilerState(Diagnostics):
    def __init__(self):
        super().__init__('Compiler', 'Compiler', 'Diagnostics for compiler', True, True, True)

    def exit(self):  # NOTE: Función temporal en lo que armamos los errores
        print(self.last_note())
        sys.exit(0)

    def process_source(self, path: Path):
        ext = path.suffix

        content = _open_file(self, path)

        ext = ext.strip('.')
        if ext == 'bg':
            frontend.BAGRON_SESSION.load()
            TKNS = frontend.BAGRON_SESSION.tokenize(content, path.name)
            return frontend.BAGRON_SESSION.parse(TKNS, path.name)
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
