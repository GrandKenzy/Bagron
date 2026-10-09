# Catalogo de Referencia del Sistema

Esta seccion contiene las especificaciones normativas de Easy-C (EGL), incluyendo la matriz completa de tipos de datos, palabras reservadas del lenguaje, clausulas de entorno del compilador y el catalogo exhaustivo de errores y diagnosticos tecnicos.

---

## Modulos y Especificaciones

* **[Tipos, Palabras Clave y Clausulas](tipos_y_palabras_clave.md):** Tablas formales de tipos primitivos, genericos, punteros, palabras reservadas y directivas de entorno (`clause`).
* **[Catalogo de Diagnosticos y Errores](errores_y_diagnostico.md):** Matriz detallada de excepciones, causas raices y procedimientos de resolucion para fallos en tiempo de compilacion.

---

## Directivas y Clausulas de Entorno (`clause`)

Easy-C utiliza la palabra clave `clause` para parametrizar la arquitectura y las restricciones del ejecutable:

| Clausula | Obligatoria | Valor por Defecto del Sistema | Descripcion |
| :--- | :--- | :--- | :--- |
| `clause Target` | Si | Ninguno (Lanza error si falta) | Identificador del backend de compilacion destino (ej. `'egl-c'`). |
| `clause Arch` | No | Arquitectura del host (`amd64`, `arm64`, `x86`) | Arquitectura de CPU destino para optimizaciones. |
| `clause System` | No | SO del host (`win`, `linux`, `darwin`) | Sistema operativo destino para adaptacion de cabeceras. |
| `clause Visibility`| No | `"public"` | Politica de visibilidad de simbolos por defecto. |
| `clause StackLimit`| No | `16384` | Limite de profundidad de la pila de llamadas. |
