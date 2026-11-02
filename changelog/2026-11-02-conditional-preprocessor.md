# Preprocesador condicional

Bagron admite bloques condicionales evaluados antes del parser:

```bg
#if OS, "windows"
func plataforma() int32:
    return 1
#elif ARCH, "amd"
func plataforma() int32:
    return 2
#else
func plataforma() int32:
    return 0
#end
```

Solo se admiten los flags `OS` y `ARCH`; `ARCH "amd"` se normaliza como
`x86_64`. Los bloques no se pueden anidar. Las ramas no seleccionadas se
reemplazan por líneas vacías antes de invocar Gram, por lo que su contenido no
se interpreta ni genera diagnósticos de sintaxis.
