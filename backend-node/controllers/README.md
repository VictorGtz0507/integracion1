# Controllers

Las acciones HTTP del monolito están concentradas actualmente en `src/routes.js`. Ese módulo cumple la responsabilidad de controlador: recibe formularios, valida la sesión, invoca los modelos y decide qué vista HTML renderizar o a qué página redirigir.

Para la estructura del curso, este directorio es el lugar recomendado para separar posteriormente controladores por área (`bookController.js`, `userController.js` y `catalogController.js`). `app.js` conserva el punto de entrada estable.