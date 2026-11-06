# 01. Flujo de compilación

El ensamblador de funciones no entra en el parser normal de Bagron. El flujo es:

1. El preprocesador detecta cada bloque `#assembler "intel"` o
   `#assembler "att"` y su correspondiente `#end`.
2. Los bloques de cada archivo `.bg` se agrupan en una unidad `.asm` dentro de
   `build/prep/`; los módulos fuente distintos conservan unidades separadas.
3. Cada función se renderiza dentro de esa unidad con su símbolo y contrato ABI.
4. Clang ensambla una vez cada unidad con el target seleccionado.
5. Los objetos resultantes se enlazan con el módulo LLVM de Bagron.

El cuerpo crudo se conserva separado de la fuente transformada; en el lugar
del bloque de función queda un `pass` para que el parser pueda analizar la
firma y el resto del cuerpo. Esto permite diagnosticar la función sin tratar
las instrucciones ASM como expresiones Bagron.

```text
fuente .bg → extracción #assembler → .asm agrupado → clang → objeto → enlace
```

Si una compilación posterior no contiene bloques ASM, el compilador limpia los
`.asm` y `.obj` anteriores dentro de `build/prep/`.
