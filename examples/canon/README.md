# Ejemplo canonico

`_main.bg` reúne las construcciones que actualmente se validan y se compilan
en un ejecutable nativo:

- globales constantes, decimales, enteros de ancho fijo, arrays, `char`, `byte`,
  `chain` estatico y punteros nulos;
- `enum`, `struct`, `mold` y `flags` con layout LLVM nominal y acceso a
  miembros locales;
- `mold` como una unión real: sus vistas comparten el mismo almacenamiento;
- `flags Nombre uint8` como campos de bits dentro de un entero explícito, con
  orden LSB por defecto y `@order_msb` cuando se requiere;
- `@packed`, `@align(N)` y `volatile` en agregados, incluyendo accesos
  volátiles y alineación explícita en el IR;
- variables locales enteras y agregadas con inicialización determinista,
  lectura y asignación compuesta;
- direcciones explícitas con `$`, desreferenciación parentizada y acceso a
  elementos de arrays locales;
- una función `@assembler` que devuelve estado mediante `EAX` y genera un
  archivo `.asm` y un objeto nativo;
- una función `sumar` y una comprobación de agregados emitidas en LLVM y
  llamadas desde `main`;
- `for` numéricos con iteradores `int32` e `int8`, rangos ascendente y descendente, y paso;
- `func main() int32` como entrypoint LLVM y código de salida.

Ejecutar desde la raíz del repositorio:

```text
vnma run main.py examples/canon/_main.bg
```

El ejecutable y el LLVM IR se generan en `examples/canon/build/`.
