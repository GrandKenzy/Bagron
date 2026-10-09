# Catalogo de Diagnosticos y Errores

Este documento recopila la totalidad de condiciones de error, diagnosticos y excepciones emitidas por el compilador de Easy-C (EGL), detallando su nivel de severidad, el subsistema emisor, su causa fundamental en el codigo fuente y la solucion tecnica correspondiente.

---

## Matriz de Diagnosticos y Excepciones

| Diagnostico / Mensaje | Nivel | Subsistema | Causa Raiz | Solucion Tecnica |
| :--- | :--- | :--- | :--- | :--- |
| `La cláusula 'Target' es obligatoria en main.egl` | Critico | Compilador | El archivo `main.egl` no declara la directiva `clause Target '<backend>'`. | Declarar `clause Target 'egl-c'` al inicio del archivo principal. |
| `No se encontró 'main.egl' en la ruta especificada` | Critico | CLI / Resolvedor | El directorio suministrado al comando `compile` no contiene un archivo `main.egl`. | Verificar la ruta del proyecto o asegurar la presencia de `main.egl`. |
| `No se encontró el módulo '<mod>' en 'source/modules/'` | Error | Modulos | Se intento importar un modulo con `import <mod>` que no existe en el disco. | Crear el archivo `source/modules/<mod>.egl` o verificar la ortografia del nombre. |
| `El módulo '<mod>' tiene un Target ('...') diferente` | Error | Modulos | Un modulo importado declara un `clause Target` incompatible con `main.egl`. | Alinear la clausula `Target` del modulo para que coincida con el target del proyecto. |
| `Librería externa '<lib>' no encontrada` | Error | Externs | Se uso `include "<lib>"` pero no existe su archivo `.externs.egl` ni en backend ni en extends. | Crear `source/targets/<backend>/extends/<lib>.externs.egl` con las firmas necesarias. |
| `Namespace '<ns>' no ha sido incluido o registrado` | Error | Externs | Se invoco `ns.metodo()` sin haber declarado `include "<lib>" as ns`. | Añadir `include "<lib>" as <ns>` en la cabecera del archivo fuente. |
| `El símbolo '<sym>' no existe en la librería/namespace` | Error | Externs | La funcion invocada no esta documentada en el archivo de externs de esa libreria. | Declarar la firma de la funcion en el archivo de externs o en `extends`. |
| `Llamada a '<ns>.<sym>' requiere al menos N argumentos`| Error | Externs | Se suministraron menos argumentos que los parametros obligatorios (sin valor por defecto). | Proveer la cantidad minima requerida de argumentos segun la firma de la funcion. |
| `Llamada a '<ns>.<sym>' recibe máximo N argumentos` | Error | Externs | Se suministraron mas argumentos que el total de parametros declarados en la firma. | Reducir los argumentos sobrantes en la invocacion. |
| `Member '.value' of type '...' is private` | Error | Backend C | Intento de acceso a la metapropiedad interna `.value` sobre una variable. | Eliminar el acceso a `.value`. Utilizar el valor de la variable directamente. |
| `Variable '<var>' is not defined, did you mean "..."?` | Error | Backend C | Se referencio un identificador inexistente con alta similitud a una variable declarada. | Corregir la variable por el nombre sugerido o declararla previamente. |
| `Variable '<var>' is of type T, but is being assigned U` | Error | Backend C | Asignacion de un tipo de dato incompatible con el tipo estatico de la variable. | Realizar conversion explicita o corregir el valor asignado. |
| `Tipo de vuelta incompatible. Se retorna T pero se esperaba U` | Error | Backend C | La sentencia `return` devuelve un tipo incompatible con la firma de la funcion. | Retornar una expresion o variable concordante con el `return_type` de la funcion. |
| `Parámetros repetidos '<param>'` | Error | Backend C | Dos o mas parametros de una funcion comparten el mismo nombre en la firma. | Renombrar los parametros duplicados para asegurar identificadores unicos. |
| `El literal de retorno ... no es compatible con el tipo` | Error | Backend C | Se retorna un literal directo cuyo tipo primitivo colisiona con el declarado. | Ajustar el literal (ej. comillas simples para `char`, enteros para `int`). |
