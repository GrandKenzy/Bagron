# Changelog 1.0.2

## Módulos y Enlace

- **Búsqueda en las carpetas base de Bagron (`modules/` y `libs/`)**:
  - `import`: Ahora revisa las carpetas canónicas `modules/` y `libs/` donde se encuentra instalado Bagron (`BAGRON_ROOT`), permitiendo que cualquier proyecto externo consuma los módulos estándar (`string`, `asmutils`, `io`, etc.) sin necesidad de copiarlos localmente.
  - Los módulos estándar importados pueden a su vez importar módulos hermanos dentro de Bagron sin generar errores de módulo fuera de la raíz del proyecto.
  - `#link`: La directiva `#link "<ruta>"` ahora revisa en el proyecto local y, en caso de no existir localmente, busca en `BAGRON_ROOT / 'libs'`, `BAGRON_ROOT / 'modules'` o en la raíz de Bagron (incluyendo prefijos `bagron/<subcarpeta>`).
  - `mangling`: Las claves internas de símbolos de módulos provenientes de `BAGRON_ROOT` se normalizan de manera canónica y determinista relativa a la instalación.

## Biblioteca Estándar

- Se incorporan los módulos base en la carpeta `modules/` del repositorio de Bagron:
  - `string.bg` (utilidades de cadenas seguras y multiplataforma con validación de trampas)
  - `asmutils.bg` (abstracción multiplataforma para trampas de ejecución y breakpoints)
  - `alphabet.bg`, `io.bg`, `math.bg`, `mem.bg`, `mmap.bg`, `os.bg`, `time.bg`

## Resolucion Semantica y Metodos

- **Llamadas a funciones de modulo desde metodos homonimos**:
  - Se corrigio la resolucion de llamadas para que cuando un metodo invoque una funcion libre o externa con el mismo nombre (por ejemplo, connect(...) dentro de Socket.connect), la llamada se resuelva hacia la funcion del modulo en lugar de interceptarse como recursion implicita sobre el metodo.
  - Storage.resolve_function_for_module y Storage.resolve_variable_for_module ahora consultan el storage raiz (_module_root()) y normalizan rutas de forma robusta.
