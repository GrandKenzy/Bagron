# Guia del Colaborador

Esta seccion contiene directrices, estandares de ingenieria y manuales paso a paso dirigidos a los desarrolladores y colaboradores que mantienen o extienden el codigo base de Easy-C (EGL). Se establecen las normas de calidad del codigo, la metodologia para incorporar nuevas construcciones sintacticas y el funcionamiento de las herramientas de consola.

---

## Modulos y Especificaciones

* **[Convenciones de Codigo](convenciones_codigo.md):** Invariantes obligatorias de ingenieria, politica estricta de comentarios en Python, convenciones de tipado estatico y directrices de inmutabilidad en el AST.
* **[Creacion de Nuevas Reglas](creacion_de_reglas.md):** Flujo de trabajo integral para implementar una nueva caracteristica del lenguaje a traves de todas las capas del compilador.
* **[CLI y Herramientas](cli_y_herramientas.md):** Arquitectura y uso del entorno de linea de comandos (`core/cli.py`, `egl.py` y `egl.bat`).

---

## Organizacion del Arbol del Proyecto

```
Easy-C/
├── core/
│   ├── backend/            <-- Generadores de codigo destino (c/)
│   ├── externs/            <-- Gestor, parser y cache de firmas foraneas
│   ├── initiator/          <-- Tokens, palabras reservadas y reglas gramaticales
│   ├── processor/          <-- Arbol de objetos semanticos y sistema de tipos
│   ├── compiler.py         <-- Orquestador monolitico y resolvedor de dependencias
│   ├── cli.py              <-- Logica del interprete de comandos
│   └── grammar.py          <-- Composicion de la gramatica formal
├── gram/                   <-- Framework de lexing y parsing combinatorio
├── source/                 <-- Directorio de trabajo y pruebas de usuario
│   ├── main.egl            <-- Archivo principal de entrada
│   ├── modules/            <-- Modulos EGL locales
│   └── targets/            <-- Extensiones del usuario (extends/)
├── docs/                   <-- Documentacion tecnica
├── egl.py                  <-- Script ejecutable raiz para CLI
└── egl.bat                 <-- Lanzador rapido para entornos Windows
```
