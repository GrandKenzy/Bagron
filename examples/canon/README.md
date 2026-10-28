# Ejemplo canonico

`_main.bg` reúne las construcciones que actualmente se validan y se compilan
en un ejecutable nativo:

- globales constantes, decimales, enteros de ancho fijo, arrays, `char`, `byte`,
  `chain` estatico y punteros nulos;
- `enum`, `struct`, `mold` y `flags` con validación semántica;
- variables locales enteras con inicialización, lectura y asignación compuesta;
- direcciones explícitas con `$`, desreferenciación parentizada y acceso a
  elementos de arrays locales;
- una función `@assembler` que devuelve estado mediante `EAX` y genera un
  archivo `.asm` y un objeto nativo;
- una función `sumar` emitida en LLVM y llamada desde `main`;
- `for` numéricos con iteradores `int32` e `int8`, rangos ascendente y descendente, y paso;
- `func main() int` como entrypoint LLVM y código de salida.

Ejecutar desde la raíz del repositorio:

```text
vnma run main.py examples/canon
```

El ejecutable y el LLVM IR se generan en `examples/canon/build/`.
