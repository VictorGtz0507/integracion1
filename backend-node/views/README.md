# Views

Las vistas HTML EJS activas están en `src/views/` porque el servidor las configura desde esa ruta. Incluyen `home.ejs`, `login.ejs`, `dashboard.ejs`, `error.ejs` y los parciales compartidos.

Este directorio documenta la convención de la clase; si se desea mover físicamente las vistas a la raíz, hay que actualizar `app.set('views', ...)` y las rutas relativas de los parciales en `src/server.js`.