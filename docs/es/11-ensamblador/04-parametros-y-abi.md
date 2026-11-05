# 04. Parámetros y ABI (Windows x64 y System V AMD64)

## 1. ¿Qué es una convención de llamada (ABI)?

Una convención de llamada o **ABI** (*Application Binary Interface*) define el estándar a bajo nivel sobre cómo se transfieren los datos entre el llamador (*caller*) y la función llamada (*callee*):
- En qué registros de la CPU se colocan los argumentos de entrada.
- En qué orden y con qué alineación se empujan los argumentos adicionales a la pila (*stack*).
- Qué registros deben ser preservados por la función llamada (*callee-saved / non-volatile*) y cuáles pueden sobreescribirse (*caller-saved / volatile*).
- En qué registro se entrega el valor de retorno (`RAX` / `EAX`).

Bagron selecciona automáticamente la convención de llamada correcta según el target del módulo:
- **Microsoft x64 ABI** cuando se compila para **Windows x64**.
- **System V AMD64 ABI** cuando se compila para **Linux**, **ELF** o **Bare-metal x86_64**.

---

## 2. ABI Windows x64 (Microsoft x64)

En el target Windows x64, los **cuatro primeros** argumentos enteros o punteros se asignan a cuatro registros dedicados. Bagron elige automáticamente el alias de ancho según el tipo declarado en la firma:

| Posición | Registro x86_64 | Propósito / Pertenencia | 64 bits (`int64`, `uint64`, `*T`) | 32 bits (`int32`, `uint32`) | 16 bits (`int16`, `uint16`) | 8 bits (`int8`, `uint8`, `byte`, `bool`) |
| --- | --- | --- | --- | --- | --- | --- |
| 1.º | `RCX` | *Counter Register* (1.er argumento) | `rcx` | `ecx` | `cx` | `cl` |
| 2.º | `RDX` | *Data Register* (2.º argumento) | `rdx` | `edx` | `dx` | `dl` |
| 3.er | `R8` | *General Purpose Register 8* (3.er argumento) | `r8` | `r8d` | `r8w` | `r8b` |
| 4.º | `R9` | *General Purpose Register 9* (4.º argumento) | `r9` | `r9d` | `r9w` | `r9b` |

### Paso por pila y *Shadow Space* en Windows x64 (argumentos 5 en adelante)
- La convención de Microsoft x64 exige que el llamador reserve siempre **32 bytes** (`0x20`) en la cima de la pila conocidos como **Shadow Space** o *Home Space* (`[rsp + 0x00]` a `[rsp + 0x18]`).
- Encima del Shadow Space se encuentran los **8 bytes** de la dirección de retorno insertada por `call`.
- Por lo tanto, el **5.º argumento** se ubica en el offset `32 + 8 = 40` bytes (`0x28`):
  - En `intel`: `[rsp + 0x28]`
  - En `att`: `40(%rsp)`
- Cada argumento posterior suma 8 bytes adicionales (`0x30`, `0x38`, etc.).

---

## 3. ABI System V AMD64 (Linux, glibc, BSD, Bare-metal ELF)

En targets Linux (`clause System "linux"` o triples `x86_64-unknown-linux-gnu`) y ELF, Bagron aplica el estándar **System V AMD64 ABI**.

Los **seis primeros** argumentos enteros o punteros se pasan por registros:

| Posición | Registro x86_64 | Propósito / Pertenencia | 64 bits (`int64`, `uint64`, `*T`) | 32 bits (`int32`, `uint32`) | 16 bits (`int16`, `uint16`) | 8 bits (`int8`, `uint8`, `byte`, `bool`) |
| --- | --- | --- | --- | --- | --- | --- |
| 1.º | `RDI` | *Destination Index* (1.er argumento) | `rdi` | `edi` | `di` | `dil` |
| 2.º | `RSI` | *Source Index* (2.º argumento) | `rsi` | `esi` | `si` | `sil` |
| 3.er | `RDX` | *Data Register* (3.er argumento) | `rdx` | `edx` | `dx` | `dl` |
| 4.º | `RCX` | *Counter Register* (4.º argumento) | `rcx` | `ecx` | `cx` | `cl` |
| 5.º | `R8` | *General Purpose Register 8* (5.º argumento) | `r8` | `r8d` | `r8w` | `r8b` |
| 6.º | `R9` | *General Purpose Register 9* (6.º argumento) | `r9` | `r9d` | `r9w` | `r9b` |

### Paso por pila en System V AMD64 (argumentos 7 en adelante)
- En System V **no existe el Shadow Space** de 32 bytes.
- Al entrar a la función, `[rsp]` contiene únicamente los 8 bytes de la dirección de retorno puesta por `call`.
- Por lo tanto, el **7.º argumento** comienza inmediatamente en el offset `0x08` (8 bytes):
  - En `intel`: `[rsp + 0x8]`
  - En `att`: `8(%rsp)`
- El 8.º argumento se ubica en `[rsp + 0x10]` / `16(%rsp)`, y así sucesivamente.

### Nota importante sobre `syscall` del Kernel Linux
Al invocar la instrucción `syscall` en Linux x86_64:
- El número de llamada al sistema se coloca en `RAX` (`%rax`).
- Los primeros 3 argumentos de función (`RDI`, `RSI`, `RDX`) y los argumentos 5.º y 6.º (`R8`, `R9`) **ya coinciden exactamente** con los registros que espera el kernel.
- Únicamente el **4.º argumento** difiere: la ABI de funciones lo recibe en `RCX`, pero la instrucción `syscall` usa `R10` (porque la propia instrucción `syscall` del procesador pisa `RCX` para guardar `RIP`). Si tu syscall usa 4 o más parámetros, basta con hacer `movq %rcx, %r10` antes de `syscall`.

## 4. Parámetros en el cuerpo ASM

Los parámetros no se interpolan en el cuerpo ASM. Bagron conserva la firma de la
función para aplicar el contrato ABI al símbolo nativo; el autor escribe
directamente los registros que corresponden al target y al ancho del parámetro:

```bg
clause System "linux"

@assembler
public func exit(code: int32) Never:
    #assembler "att"
        movq $60, %rax
        syscall
    #end
```

### Reglas del contrato ABI:
1. **Registros directos:** El cuerpo debe usar los registros de la tabla ABI sin
   placeholders ni sustituciones del compilador.
2. **Ancho declarado:** Usa el alias de registro que corresponda al tipo
   (`eax`/`edi` para un `int32`, por ejemplo).
3. **Tipos válidos:** Los parámetros no pueden ser arrays ni agregados; el
   compilador valida que sus anchos y posiciones sean representables por la ABI.
4. **Validación de instrucciones:** Bagron no comprueba si las instrucciones
   usan correctamente esos registros; Clang valida el ensamblador resultante.

## 5. System V AMD64 frente a la convención `syscall` de Linux

Estas dos convenciones están relacionadas, pero no son la misma interfaz:

| Contexto | 1.º | 2.º | 3.º | 4.º | 5.º | 6.º | Retorno |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Llamada a una función Bagron/C | `RDI` | `RSI` | `RDX` | `RCX` | `R8` | `R9` | `RAX` |
| Instrucción Linux `syscall` | `RDI` | `RSI` | `RDX` | `R10` | `R8` | `R9` | `RAX` |

Al entrar en una función llamada con System V, el primer parámetro `int32`
está en `%edi`, un puntero en `%rdi` y un parámetro `uint64` en `%rdi` o en el
registro correspondiente a su posición. Bagron no sustituye nombres de
parámetros dentro de un bloque ASM: el cuerpo debe usar estos registros
directamente.

La instrucción `syscall` destruye `%rcx` y `%r11`. Linux devuelve el resultado
en `%rax`; un valor negativo representa `-errno`. Por tanto, un wrapper que
devuelve `int64` debe usar `return asm`, mientras que una función `Never`, como
`exit`, no debe usar ningún `return`.

### Registros preservados y temporales

Una función System V puede destruir los registros temporales siguientes, salvo
que su propio contrato indique otra cosa:

| Caller-saved | Callee-saved |
| --- | --- |
| `RAX`, `RCX`, `RDX`, `RSI`, `RDI`, `R8`–`R11` | `RBX`, `RBP`, `R12`–`R15`, `RSP` |

Los registros `XMM0`–`XMM15` son también caller-saved en la ABI System V AMD64.
`RSP` debe conservarse y la pila debe respetar alineación de 16 bytes en las
llamadas normales. Los argumentos enteros que superan el sexto se encuentran
en la pila; al entrar a la función, el séptimo empieza en `8(%rsp)`.

### Syscalls Linux x86_64 usadas por `gnulibrary`

El número se carga en `%rax` antes de `syscall`:

| Función | Número | Argumentos relevantes | Retorno |
| --- | ---: | --- | --- |
| `read` | `0` | `%rdi=fd`, `%rsi=buf`, `%rdx=size` | bytes leídos o `-errno` |
| `write` | `1` | `%rdi=fd`, `%rsi=buf`, `%rdx=size` | bytes escritos o `-errno` |
| `close` | `3` | `%rdi=fd` | `0` o `-errno` |
| `getpid` | `39` | ninguno | PID o `-errno` |
| `exit` | `60` | `%rdi=code` | no retorna |

Ejemplo mínimo de `write`:

```bg
@assembler
public func write(fd: int32, buf *: byte, size: uint64) int64:
    #assembler "att"
        movq $1, %rax
        syscall
    #end
    return asm
```

El cuarto argumento de una syscall no se coloca directamente en `%rcx`:
si la función Bagron recibe cuatro parámetros, el cuarto llega en `%rcx` por
System V y debe copiarse a `%r10` antes de ejecutar `syscall`.
