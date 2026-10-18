from pathlib import Path

from gram import lexer, parser

# from tools import console, diagnostics ; pendiente
from core import processor
from core.backend import ec
from core.grammar import ENTRYPOINT
from core.processor.storage import Storage


def _open_file(source: str | Path):
    if isinstance(source, str):
        source = Path(source)

    if not source.exists():
        raise FileNotFoundError(f'El archivo no existe: {source}')


    content = source.read_text(encoding='utf-8')
    return content.splitlines(keepends=True)



def _found_main(source: Path):
    for p in source.iterdir():
        if p.is_dir():
            continue

        if p.name in ('main.egl', 'app.egl'):
            return p
    return None

class Environment:
    basedir: Path | None = None

    @classmethod
    def set(cls, base: Path):
        cls.basedir = base.absolute()


    @classmethod
    def reset(cls):
        cls.basedir = None


def compile(source: str | Path):  # only files or paths
    if isinstance(source, str):
        fd = Path(source)
    else:
        fd = source

    if not fd.exists():
        candidate = Path(str(source).replace('example/', 'examples/'))
        if candidate.exists():
            fd = candidate

    if fd.is_dir():
        Environment.set(fd)
        r = _found_main(fd)
        if not r:
            raise FileNotFoundError(f'No se encontró main.egl ni app.egl en {fd}')
        fd = r
    else:
        Environment.reset()
    return compile_source(fd)


def compile_source(fd: Path, main_storage: Storage | None = None) -> Storage:
    content = _open_file(fd)
    L = lexer.Lexer(content, logfile=fd.name)
    R = L.process()

    P = parser.Parser(R, log_file=fd.name)
    ast = P.parse(ENTRYPOINT, 'Many')

    storage = Storage(fd.absolute(), main_storage=main_storage, is_main=True)
    processor.process(storage, ast)

    # if storage.is_main:
    #     ec.compile(storage)
    # return storage