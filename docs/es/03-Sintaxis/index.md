# Sintaxis canónica

## Índice

1. [Léxico y declaraciones](01-lexico-y-declaraciones.md)
2. [Expresiones y operadores](02-expresiones-y-operadores.md)
3. [Control y funciones](03-control-y-funciones.md)
4. [Módulos, cláusulas y preprocesador](04-modulos-clausulas-y-preprocesador.md)
5. [Diagnóstico y sintaxis retirada](05-diagnostico-y-sintaxis-retirada.md)
6. [Directivas condicionales](06-directivas-condicionales.md)
7. [Directivas de enlace y librerías](07-directivas-de-enlace-y-librerias.md)
8. [Cláusulas de destino y configuración](08-clausulas-de-target.md)
9. [Directivas de ensamblador](09-directivas-de-ensamblador.md)
10. [Imports y namespaces](10-imports-y-namespaces.md)

Los archivos Bagron usan indentación significativa y declaraciones explícitas:

```bg
public limite: const int32 = 10

inline func sumar(left: int32, right: int32) int32:
    return left + right

if limite > 0:
    pass
```

Los comentarios empiezan con `;`. Los punteros separan declaración, dirección
y desreferenciación:

```bg
value: int32 = 10
pointer *: int32 = $value
(pointer) = 11
```

## Cláusulas de módulo

```bg
clause System 'windows'
clause Arch 'amd'
clause Optimizations 'prod'
```

`System`, `Arch`, `Boot`, `ABI` y `Optimizations` se validan antes de generar
LLVM.
Los módulos importados heredan el destino del módulo de entrada cuando no
declaran sus propias cláusulas. Una cláusula explícita incompatible detiene la
compilación; los imports nunca cambian el destino global.

## Formas retiradas

- `global`: las variables globales públicas se resuelven automáticamente.
- `extern "biblioteca":`: ahora se declara el dominio, por ejemplo
  `extern windows "kernel32":`.
- `package` y `package2`: la creación de librerías usa `library --v1` o
  `library --v2`.
- `@order_lsb`: LSB es el layout predeterminado; solo `@order_msb` lo cambia.

El parser conserva diagnósticos específicos para varias formas retiradas, pero
no las acepta como sintaxis funcional.
