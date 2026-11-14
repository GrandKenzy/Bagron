# Directivas condicionales

El preprocesador selecciona líneas antes del lexer y del parser de Bagron.
Solo admite una condición abierta a la vez:

```bg
#if OS, "windows"
func platform() int32:
    return 1
#elif ARCH, "amd"
func platform() int32:
    return 2
#else
func platform() int32:
    return 0
#endif
```

Las directivas válidas son `#if`, `#elif`, `#else` y `#endif`. Las condiciones
usan `OS`, `ARCH` o `ARCHB` y una cadena. `OS` compara el sistema del target;
`ARCH` normaliza alias como `amd`/`amd64`/`x86_64`, `x86`/`i386` y
`arm`/`arm64`; `ARCHB` compara el ancho de la arquitectura del target en bits:

```bg
#if ARCHB, "64"
func wide_target() int32:
    return 64
#elif ARCHB, "32"
func wide_target() int32:
    return 32
#endif
```

Las ramas no seleccionadas se reemplazan por líneas vacías para conservar las
posiciones de los diagnósticos, pero su contenido no se analiza como Bagron.
Por eso pueden contener una declaración válida solo para otro target.

No se permiten bloques anidados, condiciones compuestas ni argumentos después
de `#else` o `#endif`. Un `#elif` debe aparecer antes de `#else` y cada bloque
debe cerrarse.

`#end` queda reservado para cerrar bloques `#assembler`, por lo que un bloque
de ensamblador sí puede vivir dentro de un `#if` siempre que el condicional se
cierre con `#endif`.
