# Tools de mantenimiento

Fecha: 2026-10-29

Se añadieron dos scripts reutilizables en `tools/`:

- `cache_cleaner.py` elimina carpetas `__pycache__` y admite `--dry-run`.
- `bigfile_finder.py` informa archivos `.py` de la raíz y de `core/`, `tools/`
  y `tests/` con 500 o más líneas con contenido, ignorando comentarios y
  líneas vacías; muestra estadísticas detalladas y admite `--format json`.
  El umbral se puede cambiar con `--threshold`.
