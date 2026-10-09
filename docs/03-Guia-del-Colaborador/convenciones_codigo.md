# Convenciones de Codigo y Estandares de Ingenieria

Para asegurar la mantenibilidad, consistencia y robustez del compilador de Easy-C (EGL), todos los colaboradores deben adherirse estrictamente a las siguientes normas de desarrollo al contribuir al repositorio.

---

## Invariantes Obligatorias del Proyecto

### 1. Politica de Comentarios en Python: Cero Comentarios `#`
* **Regla Estricta:** Queda terminantemente prohibido incluir comentarios de linea iniciados con `#` en cualquiera de los archivos Python (`.py`) del proyecto.
* **Justificacion:** El codigo base debe ser completamente auto-explicativo a traves de nombres claros de variables y funciones, tipado estatico expresivo y modularizacion atomica.
* **Excepciones:** No existen excepciones en archivos `.py`. En archivos de documentacion Markdown (`.md`) o de definicion EGL (`.egl`), se utilizan las convenciones sintacticas correspondientes a cada formato (ej. `;` para comentarios en EGL).

### 2. Tipado Estatico Completo (`typing`)
* Toda funcion publica o metodo interno debe especificar anotaciones de tipo para sus parametros y su valor de retorno:
  ```python
  def resolve_source_and_main(source_path: str | Path) -> tuple[Path, Path]:
  ```
* Utilizar tipos nativos de Python 3.10+ (`list[T]`, `dict[K, V]`, `tuple[A, B]`, `str | None`).
* Evitar `Any` salvo en interfaces genericas de recorrido sintactico.

### 3. Gestion Limpia del Estado Global
* El compilador utiliza registros en memoria para almacenar objetos procesados (`base.ITEMS`), cabeceras del backend (`c.includes`, `c.typedefs`) y namespaces (`manager.namespaces`).
* Cada punto de entrada de compilacion (`compile_project`) **debe resetear el estado** al inicio para evitar contaminacion cruzada entre ejecuciones consecutivas:
  ```python
  manager.clear()
  objects.clear()
  c.clear()
  ```

### 4. Mutabilidad de Nodos AST en `gram`
* La propiedad `values` de una instancia `ASTNode` es dinamica y de solo lectura.
* Para alterar identificadores o palabras clave durante pasadas de optimizacion o mangling, **se debe mutar el valor interno del token** en `node.tokens`:
  ```python
  tok = node.tokens[0]
  tok.value = nuevo_nombre
  ```

### 5. Manejo de Rutas con `pathlib.Path`
* Queda desaconsejada la manipulacion manual de rutas mediante concatenacion de cadenas. Utilizar siempre `pathlib.Path` y sus metodos de resolucion (`resolve()`, `is_file()`, `is_dir()`, `/`).

---

## Flujo de Trabajo para Nuevas Contribuciones

1. **Crear Rama de Trabajo:** Ramificar a partir de la rama principal siguiendo nombres semanticos (`feature/nombre-caracteristica` o `fix/descripcion-error`).
2. **Implementar Cambios:** Seguir el pipeline por capas (Frontend -> Procesador -> Backend).
3. **Verificar Ausencia de Comentarios `#`:**
   Ejecutar en PowerShell para auditar el proyecto antes de enviar la contribucion:
   ```powershell
   Get-ChildItem -Recurse -Filter "*.py" | ForEach-Object {
       $file = $_.FullName
       $num = 1
       foreach ($line in Get-Content $file) {
           if ($line -match '^\s*#') { Write-Output "$file : line $num : $line" }
           $num++
       }
   }
   ```
4. **Validar Ejecucion de Pruebas:** Compilar y ejecutar el proyecto de prueba en `source`:
   ```bash
   python egl.py compile source --run
   ```
