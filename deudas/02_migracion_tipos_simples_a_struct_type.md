# Deuda Técnica 02: Migración de Tipos Simples a Definiciones Dinámicas con `Type`

## Contexto y Motivación
Actualmente, los tipos simples (`int`, `uint`, `float`, `char`, `bool`, etc.) están listados de forma fija en la lista `TYPES` de `core/initiator/keywords.py` y pre-registrados en `core/processor/type_system.py`.

La visión arquitectónica del lenguaje es que los tipos no intrínsecos no estén cableados de forma rígida en el compilador, sino que se definan dinámicamente en la librería estándar utilizando los tipos primitivos nativos (`__int_t__`, `__uint_t__`, `__float_t__`, `__char_t__`, etc.) mediante declaraciones `Type` / `struct Type`:

```egl
public struct Type int:
    __int_t__ value

public struct Type char:
    __char_t__ value
```

## Objetivos
1. Mantener únicamente los tipos intrínsecos primitivos `__*_t__` en `INTRINSIC_TYPES`.
2. Delegar la definición de aliases y tipos de alto nivel a `core/backend/c/libraries/standard.egl` (`int`, `uint`, `float`, `char`, `ptr`, `bool`, `void`, `any`, etc.).
3. Permitir que `core.processor.visitors.type_decl` los incorpore dinámicamente en `CUSTOM_TYPES` y en el grupo sintáctico `types` de `gram`.

## Estado: Completado
- Se eliminaron todos los tipos hardcodeados de `TYPES` en `core/initiator/keywords.py`, dejándolo estrictamente en `list(INTRINSIC_TYPES)`.
- Se añadieron `ptr`, `bool`, `void` y `any` mediante `public struct Type` en `standard.egl`.
- `DEFAULT_BUILTINS` en `core/processor/type_system.py` se vació por completo; la incorporación al grupo `types` ocurre dinámicamente al procesar `struct Type`.
- Se adaptaron las reglas del compilador y el desambiguador de nombres para manejar identificadores y tipos de forma posicional e idiomática sin listas fijas redundantes.
