# Pendientes

## Control de flujo

- La forma simbólica `&&`/`||` funciona en condiciones; las palabras clave
  `and`/`or` todavía requieren una integración adicional con el parser de
  expresiones.

## `#prep` y ensamblador inline

`prep` es un escape hatch de bajo nivel permitido únicamente dentro de
funciones:

```bg
#prep assembler "intel"
    nop
#end
```

Implementado en la primera fase:

- Un preprocesador previo al parser extrae el bloque crudo y conserva su
  dialecto, función y línea de origen.
- Solo las funciones marcadas con `@assembler` pueden contener el bloque; esas
  funciones quedan limitadas al bloque ASM opcional y un único `return`.
- Se rechazan bloques fuera de una función, bloques sin `#end` y cabeceras que
  no sigan el formato `#prep assembler "dialecto"`.
- Cada bloque se escribe como un archivo `.asm` independiente:
  `build/prep/<modulo>/<funcion>__prep_<indice>.asm`.
- Los placeholders `{parametro}` se sustituyen por registros u operandos de la
  ABI Windows x64 según su posición y ancho.
- `return asm` obtiene el estado desde `EAX`; el wrapper inicializa `EAX` en
  `1` y el ensamblador debe escribir `0` para éxito.
- El archivo se ensambla a `.obj` y se enlaza junto con el objeto LLVM.
- Se soportan los dialectos Intel y AT&T.
- Los placeholders infieren el alias de registro por ancho (`cl/cx/ecx/rcx` y
  equivalentes) y los parámetros desde el quinto se traducen a offsets ABI del
  stack (`rsp+0x28`, `0x30`, etc.).

Pendiente:
- Reglas avanzadas de preservación de registros, manejo manual del stack y
  llamadas nativas desde ASM.

Contrato decidido:

- La firma de la función define los parámetros de entrada; no se agregan
  `in`, `out` ni `inout` como anotaciones separadas.
- Las plantillas usan nombres (`{a}`, `{b}`), que se sustituyen por registros u
  operandos ABI antes de ensamblar.
- El resultado es el retorno normal de la ABI: para las funciones enteras
  actuales, `EAX` (`RAX` como registro físico de 64 bits). `return asm` no
  inventa otro canal de salida.
