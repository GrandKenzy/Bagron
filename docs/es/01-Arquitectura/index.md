# Arquitectura de una compilación

Bagron no genera código Python intermedio. El recorrido real es:

```text
main.py -> Compiler.compile()
        -> core/compiler/control.py
        -> core/frontend/
        -> core/storage.py
        -> core/backend/llvm/
```

`control.py` carga módulos, aplica el preprocesador y extrae `#link` o
`library` del módulo de entrada. El frontend registra declaraciones e imports,
valida tipos, ownership, punteros y layouts; después LLVM verifica el IR,
genera objetos y enlaza el target.

```powershell
vnma run main.py examples/01_basico.bg
vnma test
```

Las salidas de compilación se escriben en `build/` y son generadas. El punto de
entrada debe ser global:

```bg
func main() int32:
    return 0
```

Una función de clase llamada `main` no es entrypoint. Una llamada a una función
`Never` termina el flujo y no puede usarse como expresión.

Para instalar Bagron en Windows o Linux, consulta [Instalación del compilador
en Linux](04-instalacion-linux.md) y la guía de [Instalación de la extensión
para VS Code](03-instalacion-vscode.md). Para preparar el toolchain y probar
binarios nativos Android, consulta [Entorno Android](05-android.md).

La suite rápida cubre estas fases en `tests/test_modules.py`,
`tests/test_functions.py`, `tests/test_types.py` y `tests/test_buffer.py`.
