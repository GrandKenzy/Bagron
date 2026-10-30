# Casos límite de importaciones

Se amplían las pruebas rápidas de módulos para cubrir:

- imports selectivos con varios aliases invocables;
- rechazo de símbolos privados solicitados mediante `import { ... } from ...`;
- ciclos de tres módulos con diagnóstico de la ruta implicada;
- grafos diamante donde la dependencia compartida se carga una sola vez.

La suite se ejecuta con:

```text
vnma test tests
```
