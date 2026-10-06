## Sección nueva: microservicios, JWT y roles

Desarrolla los siguientes microservicios:
1. Users: microservicio que administre usuarios, roles, correos y contraseñas.
2. Authors: microservicio que administra autores y sus relaciones con libros.
3. Pedidos: microservicio que crea y gestiona pedidos, líneas de pedido, stock y estados.
Pagos: microservicio que registra pagos y actualiza el estado de los pedidos.
Verifica que login valide credenciales y emite un JWT firmado con SECRET_KEY, algoritmo
HS256 y expiración de 20 minutos. Debe renovarse antes de caducar.
* Users, Authors, Pedidos y Pagos: todas las operaciones POST, PUT, PATCH y DELETE deben exigir: Authorization: Bearer <JWT>
* Lecturas GET: pueden mantenerse públicas si solo consultan información; las lecturas administrativas deberían exigir JWT y permisos.
* Validación: cada servicio debe verificar firma, algoritmo, expiración y claims del token antes de modificar datos.
* Secretos: todos los servicios deben compartir JWT_SECRET_KEY, configurada mediante variables de entorno, nunca escrita directamente en el código.
* Roles: el JWT debe incluir user_id y role_id; las operaciones administrativas deben comprobar que el usuario tenga rol autorizado.
* CORS: permitir únicamente los origenes de las aplicaciones cliente en producción.
* Seguridad adicional: usar HTTPS, no guardar contraseñas ni tokens en logs y devolver 401 para tokens ausentes o inválidos y 403 para roles insuficientes.

## Sección ya seguida: Redis compartido

En el proyecto Library, agregar Redis. Redis debe incorporarse como una capa compartida para almacenar sesiones y refresh tokens, aplicar revocación de JWT, cachear consultas públicas del catálogo y coordinar tareas temporales, manteniendo PostgreSQL como fuente principal de datos; todos los microservicios deben conectarse mediante una URL común protegida y usar tiempos de
expiración coherentes.
* Añade Redis al despliegue y configura REDIS_URL=redis://:password@host:6379/0 en login, books, users, autores, pedidos y pagos.
* En login, guarda la sesión y el refresh token en Redis con TTL; conserva el JWT de acceso con expiración de 20 minutos y elimina ambos al ejecutar /logout.
* Implementa una lista de revocación en Redis usando jti como clave (jwt:revoked:<jti>) y verifica esa clave en cada servicio antes de aceptar un JWT.
* Cachea GET /books y GET /books/(isbn) con claves como books:list: filtros> y books: <isbn>, usando TTL corto; invalida esas claves después de cualquier POST, PUT, PATCH o DELETE.
* Añade manejo de desconexión, timeouts, autenticación Redis, métricas y pruebas; Redis debe ser opcional para lecturas cacheadas, pero las operaciones de sesión, revocación y autorización deben fallar de forma segura si Redis no está disponible.

Desarrolla los siguientes microservicios:

Users: microservicio que administre usuarios, roles, correos y contraseñas.

Authors: microservicio que administra autores y sus relaciones con libros.

Pedidos: microservicio que crea y gestiona pedidos, líneas de pedido, stock y estados.

Pagos: microservicio que registra pagos y actualiza el estado de los pedidos.



Verifica que login valide credenciales y emite un JWT firmado con SECRET_KEY, algoritmo HS256 y expiración de 20 minutos. Debe renovarse antes de caducar.

Users, Authors, Pedidos y Pagos: todas las operaciones POST, PUT, PATCH y DELETE deben exigir: Authorization: Bearer <JWT>

Lecturas GET: pueden mantenerse públicas si solo consultan información; las lecturas administrativas deberían exigir JWT y permisos.

Validación: cada servicio debe verificar firma, algoritmo, expiración y claims del token antes de modificar datos.

Secretos: todos los servicios deben compartir JWT_SECRET_KEY, configurada mediante variables de entorno, nunca escrita directamente en el código.

Roles: el JWT debe incluir user_id y role_id; las operaciones administrativas deben comprobar que el usuario tenga rol autorizado.

CORS: permitir únicamente los orígenes de las aplicaciones cliente en producción.

Seguridad adicional: usar HTTPS, no guardar contraseñas ni tokens en logs y devolver 401 para tokens ausentes o inválidos y 403 para roles insuficientes.