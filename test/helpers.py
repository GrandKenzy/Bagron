from pathlib import Path
from gram import lexer, parser
from core import processor
from core.grammar import ENTRYPOINT
from core.processor.storage import Storage


def compile_snippet(code: str, base_path: Path | None = None) -> Storage:
    lines = code.splitlines(keepends=True)
    if not lines:
        lines = ['']
    L = lexer.Lexer(lines)
    R = L.process()
    P = parser.Parser(R)
    ast = P.parse(ENTRYPOINT, 'Many')

    root = (base_path or Path('.')).resolve()
    storage = Storage(root)
    processor.process(storage, ast)
    return storage


def parse_snippet(code: str):
    lines = code.splitlines(keepends=True)
    if not lines:
        lines = ['']
    L = lexer.Lexer(lines)
    R = L.process()
    P = parser.Parser(R)
    return P.parse(ENTRYPOINT, 'Many')

