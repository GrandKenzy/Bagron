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
| `System` | `auto`, `linux`, `windows`, `baremetal` | sistema objetivo |
| `Arch` | `auto`, `amd`, `x86`, `arm`, `riscv32`, `riscv64` o triple LLVM | arquitectura |
| `Boot` | `none`, `multiboot2`, `uefi`, `opensbi`, `dtb`, `custom` | arranque bare-metal |
| `ABI` | `sysv_amd64` | ABI de Baremetal AMD64 |
| `Optimizations` | `dev`, `prod`, `high` | perfil LLVM |

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
