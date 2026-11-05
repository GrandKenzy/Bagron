# Cláusulas de target y configuración

`clause` sí forma parte de la gramática y usa un nombre conocido seguido de un
literal:

```bg
clause System 'windows'
clause Arch 'amd'
clause Optimizations 'prod'
```

## Target

Las cláusulas principales son:

| Cláusula | Valores relevantes | Función |
| --- | --- | --- |
| `System` | `auto`, `linux`, `windows`, `android`, `baremetal` | sistema objetivo |
| `Arch` | `auto`, `amd`, `x86`, `arm`, `riscv32`, `riscv64` o triple LLVM | arquitectura |
| `Boot` | `none`, `multiboot2`, `uefi`, `opensbi`, `dtb`, `custom` | arranque bare-metal |
| `ABI` | `sysv_amd64` | ABI de Baremetal AMD64 |
| `Optimizations` | `dev`, `prod`, `high` | perfil LLVM |

Android requiere un triple LLVM explícito y una instalación del NDK disponible
cuando se genere código nativo:

```bg
clause System "android"
clause Arch "aarch64-linux-android35"
```

Los triples iniciales soportados son `aarch64-linux-android<api>` y
`x86_64-linux-android<api>`, con API mínima 21. La forma `Arch "auto"` no es
válida para Android porque la API forma parte del target. El compilador puede
generar IR sin resolver el NDK; para objetos, ensamblador o ejecutables se
requiere `ANDROID_NDK_HOME` o `ANDROID_NDK_ROOT`. La configuración del NDK,
la verificación del ELF y las pruebas con `adb` se documentan en [Entorno
Android](../01-Arquitectura/05-android.md).

El resultado es un ejecutable ELF nativo; Bagron no genera APK en esta etapa.
`--execute` no ejecuta binarios Android cruzados en el host de compilación.

`baremetal` exige `Boot` y `ABI` explícitos. La única ABI admitida actualmente
es `sysv_amd64`, y solo puede usarse con arquitectura AMD64. `Boot` distinto de
`none` no es válido en Linux o Windows. `multiboot2` solo está soportado
actualmente para x86/i386 y x86-64; `opensbi` requiere RISC-V y `uefi` una
arquitectura compatible.

El módulo de entrada selecciona un único target. Los módulos importados que no
declaran una cláusula de target heredan el valor del módulo de entrada; no son
un caso especial ni generan warnings. Si un módulo importado declara `System`,
`Arch`, `Boot` o `ABI`, su valor debe ser compatible con el target y la ABI
principales. Una declaración explícita incompatible rechaza la compilación. Una cláusula
`System`, `Arch`, `Boot`, `ABI` u `Optimizations` repetida también es un error.

`ABI` solo es válida cuando el target efectivo es `baremetal`. No define una
convención arbitraria: selecciona una ABI conocida por el compilador. Una
configuración Baremetal AMD64 completa es:

```bg
clause System "baremetal"
clause Arch "amd"
clause Boot "none"
clause ABI "sysv_amd64"
```

## Cláusulas aceptadas de almacenamiento

`Privacy` acepta `public` o `private`, y `StackLimit` acepta un número. El
frontend las valida y las registra en el almacenamiento del compilador, pero no
son sustitutos de los modificadores `public`/`private` ni forman parte de la
selección de target. `StackLimit` no constituye por sí solo una comprobación de
runtime en el backend actual.
