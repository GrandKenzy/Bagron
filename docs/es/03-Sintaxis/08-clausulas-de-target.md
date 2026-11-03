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
| `Optimizations` | `dev`, `prod`, `high` | perfil LLVM |

`baremetal` exige `Boot` explícito. `Boot` distinto de `none` no es válido en
Linux o Windows. `multiboot2` solo está soportado actualmente para x86/i386 y
x86-64; `opensbi` requiere RISC-V y `uefi` una arquitectura compatible.

El módulo de entrada selecciona un único target. Los módulos importados pueden
omitir dimensiones y quedan agnósticos, pero una cláusula explícita incompatible
con el target principal rechaza la compilación. Una cláusula `System`, `Arch`,
`Boot` u `Optimizations` repetida también es un error.

## Cláusulas aceptadas de almacenamiento

`Privacy` acepta `public` o `private`, y `StackLimit` acepta un número. El
frontend las valida y las registra en el almacenamiento del compilador, pero no
son sustitutos de los modificadores `public`/`private` ni forman parte de la
selección de target. `StackLimit` no constituye por sí solo una comprobación de
runtime en el backend actual.
