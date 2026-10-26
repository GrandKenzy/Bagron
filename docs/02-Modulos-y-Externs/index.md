# Sistema De Modulos, Externs Y Extends

Este documento describe la arquitectura modular del compilador **Bagron**, el mecanismo de resolucion topologica de dependencias y el subsistema de contratos externos.

---

## Modulos Y Resolucion De Dependencias

Bagron permite estructurar proyectos en multiples archivos `.bg` mediante la directiva `import`:

- **Directiva `import`:** Importa un modulo escrito en Bagron. El analizador semantico procesa el archivo indicado, construye su tabla `Storage` y valida los tipos de sus simbolos publicos.

### Prevencion De Recursion (`in_progress`)
Al procesar un modulo, el compilador registra su ruta canonica en el conjunto `storage.in_progress`. Si durante la construccion de dependencias un submodulo intenta importar un ancestro que aun no ha finalizado su analisis semantico, el compilador detecta el ciclo inmediatamente y evita bloqueos en memoria.

### Linearizacion Topologica (`ordered_modules`)
Cada vez que un modulo culmina exitosamente su procesamiento semantico, se incorpora a la lista `storage.ordered_modules`:

```
       [ main.bg ]
        /        \
       v          v
   [ math.bg ]  [ vector.bg ]
        \        /
         v      v
      [ common.bg ]

   orden de resolucion:
   - common.bg
   - math.bg
   - vector.bg
   - main.bg
```

Este ordenamiento garantiza que cualquier definicion requerida por el modulo principal ya este resuelta previamente.
