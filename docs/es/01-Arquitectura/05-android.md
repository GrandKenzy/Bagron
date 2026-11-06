# Entorno Android

Esta guía describe el estado actual del soporte Android de Bagron y el flujo
para generar y probar ejecutables nativos. La sintaxis de las cláusulas se
documenta en [Cláusulas de target y configuración](../03-Sintaxis/08-clausulas-de-target.md).

## Estado actual

Bagron puede generar un ejecutable ELF nativo para Android mediante el NDK.
Android se trata como un target distinto de Linux y necesita un triple LLVM
explícito:

| ABI | Triple de ejemplo | Resultado esperado |
| --- | --- | --- |
| ARM64 | `aarch64-linux-android35` | `EM_AARCH64` |
| x86-64 | `x86_64-linux-android35` | `EM_X86_64` |

La API mínima admitida actualmente es 21. La API 35 es la configuración
validada en el entorno de desarrollo actual. `Arch "auto"` no se admite para
Android porque la API forma parte del triple.

El soporte todavía no incluye generación de APK, integración con el framework
Android, Java/Kotlin, instalación automática ni ejecución mediante
`--execute`. El resultado debe copiarse y ejecutarse con `adb` en un
dispositivo o emulador compatible.

## Requisitos del entorno

Para generar objetos o ejecutables Android se necesita un Android NDK. El
resolvedor interno busca `ANDROID_NDK_HOME` y, como alternativa,
`ANDROID_NDK_ROOT`; después valida el triple, selecciona `clang.exe` y
`ld.lld.exe`, y obtiene el sysroot y las bibliotecas de la API solicitada.

La instalación validada en el entorno de desarrollo usa esta distribución en
`E:`:

```text
E:\Android\Sdk
└── ndk\30.0.16248370
```

En PowerShell, configura el NDK para la sesión antes de compilar:

```powershell
$env:ANDROID_NDK_HOME = 'E:\Android\Sdk\ndk\30.0.16248370'
$env:ANDROID_NDK_ROOT = $env:ANDROID_NDK_HOME
```

El SDK completo no es necesario para la compilación LLVM. Para desplegar el
resultado se necesita además `platform-tools`, que en esta instalación contiene
`E:\Android\Sdk\platform-tools\adb.exe`. Puede añadirse esa carpeta al `PATH`
o invocarse `adb.exe` mediante su ruta absoluta.

## Compilación

El módulo debe declarar el sistema y el triple de forma explícita:

```bg
clause System "android"
clause Arch "x86_64-linux-android35"

func main() int32:
    return 0
```

Para compilar para el target x86-64:

```powershell
bagron <archivo.bg> -o build\android-x86_64
```

Para ARM64 cambia la cláusula y el nombre de salida:

```bg
clause System "android"
clause Arch "aarch64-linux-android35"
```

```powershell
bagron <archivo.bg> -o build\android-aarch64
```

El backend puede producir IR sin resolver el NDK. La variable de entorno es
obligatoria cuando la salida requiere ensamblado, objeto o ejecutable nativo.

## Verificación del ELF

Antes de transferir el archivo, comprueba la arquitectura generada con las
herramientas del NDK:

```powershell
$llvmReadobj = "$env:ANDROID_NDK_HOME\toolchains\llvm\prebuilt\windows-x86_64\bin\llvm-readobj.exe"
& $llvmReadobj --file-headers .\build\android-x86_64
```

El encabezado debe mostrar `EM_X86_64` para `x86_64-linux-android35` o
`EM_AARCH64` para `aarch64-linux-android35`. Esta comprobación detecta un
triple o una salida equivocada antes de involucrar al dispositivo.

## Despliegue con `adb`

El flujo mínimo para probar un ejecutable es:

```powershell
$adb = 'E:\Android\Sdk\platform-tools\adb.exe'
& $adb devices
& $adb push .\build\android-x86_64 /data/local/tmp/bagron-test
& $adb shell chmod 755 /data/local/tmp/bagron-test
& $adb shell /data/local/tmp/bagron-test
```

Usa un dispositivo o emulador cuya ABI coincida con el ELF. Un binario ARM64
requiere un dispositivo `arm64-v8a` o un entorno que ofrezca una capa de
compatibilidad; un binario x86-64 requiere `x86_64`.

## Emuladores en Windows

En un host Windows x86-64, el AVD x86-64 es la opción directa para probar
`x86_64-linux-android35`. Algunas imágenes x86-64 también anuncian
`arm64-v8a` mediante Native Bridge y permiten ejecutar un ELF ARM64, pero esa
capacidad depende de la imagen y no sustituye una prueba en hardware ARM64.

Un AVD `arm64` no puede arrancar mediante QEMU2 en un host x86-64. Para
probarlo se necesita hardware ARM64 o un host con esa arquitectura.

Si el SDK o los AVD se movieron a `E:` y el emulador informa `Broken AVD
system path`, comprueba que `ANDROID_SDK_ROOT` apunte al SDK nuevo. Como
solución explícita para una imagen x86-64:

```powershell
$env:ANDROID_SDK_ROOT = 'E:\Android\Sdk'
$emulator = 'E:\Android\Sdk\emulator\emulator.exe'
$sysdir = 'E:\Android\Sdk\system-images\android-35\google_apis\x86_64'
& $emulator -avd Bagron_API35_x86_64 -sysdir $sysdir
```

El parámetro `-sysdir` es una ayuda para configuraciones con rutas antiguas;
no forma parte del target ni del compilador.

## Límites conocidos

- Solo están implementados inicialmente `aarch64-linux-android<api>` y
  `x86_64-linux-android<api>`.
- El NDK resuelve la toolchain y el sysroot, pero Bagron todavía no valida
  semánticamente que el código ensamblador externo sea portable a Android.
- La salida es un ELF nativo, no un APK.
- No se genera automáticamente manifiesto, firma, `adb install` ni paquete de
  aplicación.
- La ejecución cruzada con `--execute` se rechaza de forma explícita.
