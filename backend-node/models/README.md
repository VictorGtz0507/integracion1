# Models

Los modelos activos están en `src/models/`:

- `userModel.js`: usuarios, hash de contraseñas y autenticación.
- `catalogModel.js`: libros, autores, categorías, relaciones, conceptos e imágenes.

Estos módulos contienen el acceso directo a SQLite. No devuelven JSON: entregan datos a los controladores para renderizar vistas EJS.