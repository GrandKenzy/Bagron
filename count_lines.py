import os
from collections import defaultdict

# Extensiones binarias comunes a omitir para no contar basura de archivos binarios
BINARY_EXTENSIONS = {'.dll', '.exe', '.so', '.dylib', '.a', '.lib', '.bin', '.pyc', '.pyd', '.png', '.jpg', '.ico'}

# Carpetas y extensiones a excluir según la solicitud
EXCLUDED_DIRS = {'__pycache__', '.git'}
EXCLUDED_EXTENSIONS = {'.md'}

def is_binary_file(filepath: str) -> bool:
    """Verifica si un archivo es binario leyendo un fragmento inicial."""
    _, ext = os.path.splitext(filepath)
    if ext.lower() in BINARY_EXTENSIONS:
        return True
    try:
        with open(filepath, 'rb') as f:
            chunk = f.read(1024)
            if b'\x00' in chunk:
                return True
    except Exception:
        return True
    return False

def count_lines(root_dir: str = '.'):
    total_lines = 0
    total_files = 0
    lines_by_ext = defaultdict(int)
    files_by_ext = defaultdict(int)
    lines_by_dir = defaultdict(int)
    files_by_dir = defaultdict(int)

    for root, dirs, files in os.walk(root_dir):
        # Excluir directorios ignorados
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]

        rel_dir = os.path.relpath(root, root_dir)
        top_dir = rel_dir.split(os.sep)[0] if rel_dir != '.' else '.'

        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in EXCLUDED_EXTENSIONS:
                continue

            filepath = os.path.join(root, file)
            if is_binary_file(filepath):
                continue

            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    count = sum(1 for _ in f)
                    total_lines += count
                    total_files += 1

                    ext_key = ext if ext else '[sin extensión]'
                    lines_by_ext[ext_key] += count
                    files_by_ext[ext_key] += 1

                    lines_by_dir[top_dir] += count
                    files_by_dir[top_dir] += 1
            except Exception as e:
                print(f"No se pudo leer {filepath}: {e}")

    return {
        'total_lines': total_lines,
        'total_files': total_files,
        'by_ext': {
            ext: (lines_by_ext[ext], files_by_ext[ext])
            for ext in sorted(lines_by_ext.keys(), key=lambda x: lines_by_ext[x], reverse=True)
        },
        'by_dir': {
            d: (lines_by_dir[d], files_by_dir[d])
            for d in sorted(lines_by_dir.keys(), key=lambda x: lines_by_dir[x], reverse=True)
        }
    }

if __name__ == '__main__':
    results = count_lines('.')
    
    print('=' * 60)
    print(f" TOTAL DE LÍNEAS EN EL PROYECTO: {results['total_lines']:,} líneas ({results['total_files']} archivos)")
    print(' (Excluyendo __pycache__, .md, .git y binarios)')
    print('=' * 60)

    print("\nDesglose por extensión:")
    print("-" * 60)
    for ext, (lines, count) in results['by_ext'].items():
        print(f" {ext:16} : {lines:8,} líneas  ({count:3} archivos)")

    print("\nDesglose por carpeta:")
    print("-" * 60)
    for d, (lines, count) in results['by_dir'].items():
        print(f" {d:16} : {lines:8,} líneas  ({count:3} archivos)")
    print("=" * 60)
