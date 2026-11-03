# 01. Flujo de compilación

El ensamblador preparado no entra en el parser normal de Bagron. El flujo es:

1. `core/compiler/prep.py` detecta cada `#prep assembler ... #end`.
2. El bloque se extrae a un archivo `.asm` dentro de `build/prep/`.
3. Los bloques de función se renderizan con su símbolo y contrato ABI.
4. Clang ensambla el archivo con el target seleccionado.
5. El objeto resultante se enlaza con el módulo LLVM de Bagron.

El cuerpo crudo se conserva separado de la fuente transformada; en el lugar
del bloque de función queda un `pass` para que el parser pueda analizar la
firma y el resto del cuerpo. Esto permite diagnosticar la función sin tratar
las instrucciones ASM como expresiones Bagron.

```text
fuente .bg → extracción #prep → archivo .asm → clang → objeto → enlace
```

Si una compilación posterior no contiene bloques preparados, el compilador
limpia los `.asm` y `.obj` preparados anteriores dentro de `build/prep/`.
