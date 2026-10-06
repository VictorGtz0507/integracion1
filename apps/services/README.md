# Microservicios Library

Los servicios Flask son procesos independientes que usan PostgreSQL como fuente principal. Redis ofrece sesiones, refresh tokens, revocación de JWT, caché temporal del catálogo y coordinación de locks. Los nuevos servicios usan el módulo común `shared.jwt_auth` para verificar HS256, expiración, claims (`user_id`, `role_id`, `jti`), revocación y rol.

## Servicios y rutas

| Servicio | Puerto por defecto | Funcionalidad |
|---|---:|---|
| `login` | 5000 | Registro, login, sesión, logout, refresh de tokens |
| `soap` (Books) | 5001 | Catálogo público y CRUD de libros para administradores |
| `users` | 5002 | Perfil propio; administración de usuarios y roles para administradores |
| `authors` | 5003 | Consulta pública de autores/libros; CRUD y relaciones para administradores |
| `pedidos` (Orders) | 5004 | Órdenes propias, reserva de stock y transiciones de estado administrativas |
| `pagos` (Payments) | 5005 | Consulta propia, registro del ledger y reembolso administrativo |

Las escrituras requieren `Authorization: Bearer <JWT>`; la administración requiere `role=admin`. Las lecturas de usuarios y órdenes siempre comprueban propiedad o rol. Las lecturas GET de libros y autores son públicas.

Rutas nuevas:

- Users: `GET /users/me`; admin `GET /users`, `GET /users/<id>`, `GET /roles`, `POST /users`, `PUT/PATCH /users/<id>`, `DELETE /users/<id>`.
- Authors: público `GET /authors`, `GET /authors/<id>`; admin `POST /authors`, `PUT/PATCH/DELETE /authors/<id>`, `POST /authors/<id>/books`, `DELETE /authors/<id>/books/<book_id>`.
- Orders: `GET /orders`, `GET /orders/<id>` (propietario/admin); `POST /orders` crea una orden con `items: [{"book_id": 1, "quantity": 2}]` y reserva stock en una transacción; admin puede cambiar estados con `PUT/PATCH /orders/<id>` o eliminar órdenes pendientes.
- Payments: `GET /payments` y `GET /payments/<id>` (propietario/admin); `POST /payments` recibe `{"order_id": 1, "method": "manual"}`; admin puede marcar reembolsos con `PUT/PATCH /payments/<id>` y `{"status":"refunded"}`.

El servicio Payments es un ledger de demostración: marca un pago como exitoso y actualiza la orden atómicamente, pero no se conecta a Stripe/PayPal ni procesa tarjetas. No enviar datos de tarjeta. Integrar un proveedor real requiere webhooks autenticados e idempotencia del proveedor.

El esquema añadido está en `apps/services/schema.sql` y se aplica de forma idempotente al iniciar Users, Authors, Orders o Payments. Migra `auth_users.role_id` y crea roles `admin`, `staff`, `customer`, además de `orders`, `order_items` y `payments`; no reemplaza las tablas existentes de Books. Las tablas `books`, `authors` y `book_authors` deben existir previamente según el esquema PostgreSQL que usa Books.

Las cuentas existentes se migran al rol menos privilegiado `customer`. Para habilitar administradores, el DBA debe promover explícitamente una cuenta de confianza después de iniciar Login:

```sql
UPDATE auth_users
SET role_id = (SELECT role_id FROM roles WHERE role_name = 'admin')
WHERE email = 'correo-administrador-verificado@example.com';
```

No se autoeleva ninguna cuenta durante el registro.

## Despliegue de Redis protegido

Desde la raíz del repositorio, copia las plantillas únicamente para servicios que aún no tengan `.env` (no reemplaces archivos existentes):

```powershell
$serviceNames = @('login', 'soap', 'users', 'authors', 'pedidos', 'pagos')
foreach ($name in $serviceNames) {
	$directory = "apps/services/$name"
	if (-not (Test-Path "$directory/.env")) {
		Copy-Item "$directory/.env.example" "$directory/.env"
	}
}
if (-not (Test-Path 'apps/services/.env')) {
	Copy-Item apps/services/.env.example apps/services/.env
}
```

En Linux/CentOS Stream 10, desde la raíz:

```bash
for name in login soap users authors pedidos pagos; do
  test -f "apps/services/$name/.env" || cp "apps/services/$name/.env.example" "apps/services/$name/.env"
done
test -f apps/services/.env || cp apps/services/.env.example apps/services/.env
```

Edita `apps/services/.env` y configura un `REDIS_PASSWORD` largo y aleatorio. Inicia Redis:

```powershell
docker compose --env-file apps/services/.env -f apps/services/redis.compose.yaml up -d
```

En Linux usa los mismos comandos, sustituyendo `Copy-Item` por `cp`. Compose solo publica Redis en loopback del host. Los procesos de Flask que corren directamente en la VM usarán `localhost`; si se ejecutan dentro de contenedores, configura el host como el nombre DNS del servicio Redis en su red privada.

Configura `REDIS_URL=redis://:PASSWORD@HOST:6379/0` en los `.env` de los seis servicios, sustituyendo los valores reales. `REDIS_URL` es obligatorio para iniciar Login y para aceptar operaciones protegidas; las lecturas públicas del catálogo pueden seguir por PostgreSQL sin Redis. Los ejemplos usan placeholders deliberadamente y nunca deben ser usados como secretos de producción. Si la contraseña contiene caracteres reservados en URL (`@`, `:`, `/`, `#`, `%`), codifícala como URL component. La URL protegida nunca debe incluirse en Git. Configura exactamente el mismo `JWT_SECRET_KEY` criptográficamente aleatorio en los seis `.env`; los servicios ya no aceptan el nombre legado `JWT_SECRET`.

Completa en cada `.env` las mismas credenciales PostgreSQL, el mismo `JWT_SECRET_KEY`, el `REDIS_URL` protegido y los orígenes permitidos. Para instalar cada servicio en un entorno aislado de Windows:

```powershell
$serviceNames = @('login', 'soap', 'users', 'authors', 'pedidos', 'pagos')
foreach ($name in $serviceNames) {
	Push-Location "apps/services/$name"
	py -m venv .venv
	.\.venv\Scripts\python.exe -m pip install -r requirements.txt
	Pop-Location
}
```

En Linux/CentOS Stream 10:

```bash
for name in login soap users authors pedidos pagos; do
	(cd "apps/services/$name" && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt)
done
```

Arranca cada `app.py` desde su propia carpeta/terminal y conserva los puertos de la tabla. Por ejemplo, en seis terminales, ejecuta `cd apps/services/login; .\.venv\Scripts\python.exe app.py`, cambiando el servicio en cada terminal. Login y los servicios nuevos aplican las tablas aditivas al arrancar; Books requiere las tablas de catálogo ya existentes. Para producción, define `APP_ENV=production`, publica únicamente detrás de HTTPS (reverse proxy), configura `CORS_ORIGINS` como la lista separada por comas de dominios exactos permitidos, y activa `SESSION_COOKIE_SECURE=true` en Login. Los servicios fallan al iniciar si production carece de allowlist CORS. El servidor de desarrollo de Flask no es para producción.

## Contratos y expiraciones

- Access JWT firmado exclusivamente con HS256 y `JWT_SECRET_KEY`: 1200 s (20 minutos), con `user_id`, `role_id`, `role`, `jti`, `iat`, `exp` y `sub` obligatorios y coherentes. No hay clave JWT de fallback en código. Login ofrece `POST /refresh` para rotar el refresh token y emitir un access token nuevo; el cliente debe solicitarlo antes del vencimiento.
- Sesión de login y refresh token: 604800 s (7 días), configurables mediante variables de entorno.
- Cache de libros: 60 s por defecto; configurable con `BOOKS_CACHE_TTL_SECONDS`.
- Revocación: `jwt:revoked:<jti>` expira después del tiempo restante del access token.
- Refresh tokens: valor opaco aleatorio, almacenado bajo un SHA-256 (`jwt:refresh:<digest>`), consumo de un solo uso y rotación en `POST /refresh`.

Las sesiones de Flask se almacenan con Flask-Session en Redis. `POST /logout` revoca el access token de la sesión, borra su refresh token y destruye la sesión. `GET /session`, login, refresh y escrituras protegidas requieren Redis; ante una caída devuelven error y no continúan sin verificar autenticación.

## Seguridad de publicación

- Tokens ausentes, firma/algoritmo/expiración/claims inválidos o `jti` revocado: `401`.
- Token válido con rol insuficiente: `403`.
- Redis inaccesible durante login, sesión, refresh, revocación o autorización: `503`, sin continuar con una operación protegida.
- No registrar cuerpos de login, contraseñas, JWT, refresh tokens ni encabezados `Authorization`. Los errores de Login devuelven mensajes genéricos, no detalles de base de datos.
- En producción configura `APP_ENV=production`, HTTPS en un proxy inverso y `SESSION_COOKIE_SECURE=true`. `CORS_ORIGINS` debe listar únicamente los orígenes HTTPS exactos del cliente, separados por comas; sin esa lista el proceso se niega a arrancar.
- Los `.env.example` son plantillas: en cada `.env` real establece `SECRET_KEY`, el mismo `JWT_SECRET_KEY` en los seis servicios, `REDIS_URL` autenticada, `APP_ENV` y `CORS_ORIGINS`. La clave de cookie `SECRET_KEY` de Login es independiente de `JWT_SECRET_KEY`.

## Caché y consistencia

Books cachea listas y búsquedas bajo `books:list:<hash-de-filtros>` y detalles ISBN bajo `books:<isbn>`. La caché solo acelera lecturas públicas; si Redis falla, esas lecturas consultan PostgreSQL. Tras escritura confirmada, se borran las claves `books:*` con `SCAN` (no `KEYS`); el TTL corto limita datos obsoletos ante una desconexión o fallo de invalidación.

Los locks distribuidos disponibles en `shared.redis_support.acquire_task_lock(name, ttl_seconds)` coordinan una única ejecución temporal con una clave `task:lock:<name>` y expiración automática. El proyecto aún no tiene workers/jobs que los necesiten, por lo que no se inventó un proceso de pedidos/pagos.

## Salud y métricas

- `GET /health` y `GET /metrics` están disponibles en los seis servicios.
- `GET /metrics` expone contadores y latencias agregadas de sesiones/refresh/revocación, caché del catálogo y locks, junto a memoria Redis cuando está disponible.
- `REDIS_CONNECT_TIMEOUT` y `REDIS_SOCKET_TIMEOUT` limitan la espera (2 s por defecto).
- Redis usa contraseña, volumen persistente AOF, límite de memoria y política `noeviction` en Compose. `noeviction` evita descartar sesiones/revocaciones; cuando se agota la memoria, escrituras críticas fallan y la autenticación queda cerrada. Ajusta memoria según el entorno; no expongas el puerto a Internet.

## Pruebas

Con dependencias instaladas, desde la raíz ejecuta las pruebas con los entornos que contienen Flask/Psycopg/Redis:

```powershell
apps/services/login/.venv/Scripts/python.exe -m unittest discover -s apps/services/shared/tests
apps/services/login/.venv/Scripts/python.exe -m unittest discover -s apps/services/login/tests
apps/services/soap/.venv/Scripts/python.exe -m unittest discover -s apps/services/soap/tests
apps/services/login/.venv/Scripts/python.exe -m unittest discover -s apps/services/users/tests
apps/services/login/.venv/Scripts/python.exe -m unittest discover -s apps/services/authors/tests
apps/services/login/.venv/Scripts/python.exe -m unittest discover -s apps/services/pedidos/tests
apps/services/login/.venv/Scripts/python.exe -m unittest discover -s apps/services/pagos/tests
```

Las pruebas de unidad no requieren servicios vivos. Para prueba integrada, inicia Redis y PostgreSQL con el esquema existente, luego prueba login, refresh, logout, `GET /api/books` y `POST /api/books` con Bearer token. `POST /refresh` recibe `{"refresh_token":"..."}`.