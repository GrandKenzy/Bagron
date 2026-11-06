# Arquitectura de una compilación

Bagron compila directamente código fuente `.bg` a código nativo sin generar
Python intermedio ni requerir una máquina virtual. El pipeline de compilación es:

```text
Fuente (.bg)
   ↓
Preprocesador de directivas (#assembler, #link, condicionales)
   ↓
Frontend semántico (símbolos, tipos estrictos, ownership, layouts)
   ↓
Backend LLVM (generación y verificación de IR, optimizaciones)
   ↓
Emisión de objeto y enlace nativo (ejecutable o biblioteca .lib)
```

El preprocesador carga los módulos, resuelve dependencias nativas `#link` y
cláusulas de biblioteca `library`. El frontend registra las declaraciones,
comprueba la visibilidad `public`/`private`, valida tipos estrictos, layouts de
agregados y reglas de ownership en buffers y descriptores `opaque`. Posteriormente,
el backend genera LLVM IR verificado, aplica el pipeline de optimizaciones
según el perfil (`prod`, `dev` o `high`) y enlaza el artefacto para el target.

Para compilar y ejecutar un programa desde la línea de comandos:

```powershell
bagron examples/01_basico.bg -o build/ejemplo --execute
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

El compilador asegura de forma estricta la coherencia de módulos,
declaraciones, firmas, contratos de ownership y tipos antes de emitir código nativo.
