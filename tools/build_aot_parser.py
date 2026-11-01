"""Exporta y compila el parser C de Gram que produce GIR para Bagron.

El ejecutable resultante solo cubre lexer/parser y serialización GIR. Bagron
continúa ejecutando sus pasadas semánticas y su backend LLVM en Python.
"""

from __future__ import annotations

import argparse
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path


def _load_gram_exporter(gram_path: Path) -> None:
    """Evita que ``Bagron/tools`` oculte el exportador de ``Gram/tools``."""
    exporter_path = gram_path / 'tools' / 'export_lexer_tables.py'
    if not exporter_path.is_file():
        raise FileNotFoundError(f'No existe el exportador de Gram: {exporter_path}')

    spec = importlib.util.spec_from_file_location(
        'tools.export_lexer_tables',
        exporter_path,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f'No se pudo cargar el exportador de Gram: {exporter_path}')
    module = importlib.util.module_from_spec(spec)
    sys.modules['tools.export_lexer_tables'] = module
    spec.loader.exec_module(module)


def _find_clang(configured: str | None) -> Path:
    candidates = []
    if configured:
        candidates.append(Path(configured).expanduser())
    resolved = shutil.which('clang')
    if resolved:
        candidates.append(Path(resolved))
    if sys.platform == 'win32':
        candidates.append(Path(r'C:\Program Files\LLVM\bin\clang.exe'))

    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError(
        'No se encontró Clang; usa --clang <ruta> para indicar el compilador C11.'
    )


def build_parser(gram_path: Path, output_dir: Path, clang: str | None) -> Path:
    """Exporta la sesión de Bagron y compila su driver GIR autónomo."""
    gram_path = gram_path.resolve()
    output_dir = output_dir.resolve()
    repository_root = Path(__file__).resolve().parents[1]
    output_dir.mkdir(parents=True, exist_ok=True)
    clang_path = _find_clang(clang)

    repository_text = str(repository_root)
    if repository_text not in sys.path:
        sys.path.insert(0, repository_text)
    gram_text = str(gram_path)
    if gram_text not in sys.path:
        sys.path.insert(0, gram_text)
    _load_gram_exporter(gram_path)

    from core import frontend

    manifest = frontend.BAGRON_SESSION.export_c_parser(
        output_dir,
        emit_driver=True,
        emit_cli=True,
    )

    lexer_root = gram_path / 'native' / 'gram_lexer'
    include_dir = lexer_root / 'include'
    lexer_source_dir = lexer_root / 'src'
    generated_sources = sorted(output_dir.glob('gram_*.c'))
    lexer_sources = sorted(lexer_source_dir.glob('*.c'))
    if not generated_sources:
        raise RuntimeError(f'Gram no generó unidades C en {output_dir}')
    if not lexer_sources:
        raise RuntimeError(f'No hay runtime lexer C en {lexer_source_dir}')

    executable_name = 'bagron_aot.exe' if sys.platform == 'win32' else 'bagron_aot'
    executable = output_dir / executable_name
    command = [
        str(clang_path),
        '-std=c11',
        '-O2',
        f'-I{include_dir}',
        f'-I{lexer_source_dir}',
        f'-I{output_dir}',
        *(str(path) for path in generated_sources),
        *(str(path) for path in lexer_sources),
        '-o',
        str(executable),
    ]
    result = subprocess.run(command, check=False)
    if result.returncode:
        raise RuntimeError(f'Clang terminó con código {result.returncode}.')

    ffi_source = repository_root / 'tools' / 'bagron_aot_ffi.c'
    if not ffi_source.is_file():
        raise FileNotFoundError(f'No existe el wrapper GIR: {ffi_source}')
    library_name = {
        'win32': 'bagron_aot.dll',
        'darwin': 'bagron_aot.dylib',
    }.get(sys.platform, 'libbagron_aot.so')
    library = output_dir / library_name
    library_command = [
        str(clang_path),
        '-shared',
        '-O2',
        f'-I{include_dir}',
        f'-I{lexer_source_dir}',
        f'-I{output_dir}',
        str(ffi_source),
        *(str(path) for path in generated_sources if path.name != 'gram_cli.c'),
        *(str(path) for path in lexer_sources),
        '-o',
        str(library),
    ]
    library_result = subprocess.run(library_command, check=False)
    if library_result.returncode:
        raise RuntimeError(
            f'Clang no pudo crear la biblioteca GIR; terminó con código '
            f'{library_result.returncode}.'
        )

    print(f'grammar_id={manifest.get("grammar_id", "unknown")}')
    print(f'output={executable}')
    print(f'shared_library={library}')
    return executable


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Construye el parser AOT de Gram que produce GIR para Bagron.'
    )
    parser.add_argument(
        '--gram-path',
        type=Path,
        default=Path.home() / 'Desktop' / 'Gram',
        help='Checkout editable de Gram (por defecto: ~/Desktop/Gram)',
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path(__file__).resolve().parents[1] / 'build' / 'aot',
        help='Directorio generado para C/GIR y el ejecutable',
    )
    parser.add_argument(
        '--clang',
        help='Ruta explícita a clang; si se omite se busca en PATH y LLVM de Windows',
    )
    args = parser.parse_args()

    try:
        build_parser(args.gram_path, args.output_dir, args.clang)
    except (FileNotFoundError, ImportError, RuntimeError) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
