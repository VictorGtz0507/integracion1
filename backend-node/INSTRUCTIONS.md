# Instrucciones de Lumen / Librería

## 1. Propósito

Esta aplicación es un monolito Node.js para administrar un catálogo de libros. Todo vive en un único proceso:

1. El navegador envía una petición HTTP o un formulario HTML.
2. Express recibe la petición y ejecuta una ruta.
3. La ruta valida la sesión y delega la operación al modelo.
4. El modelo consulta o modifica la base de datos.
5. Express renderiza una vista EJS y devuelve HTML al navegador.

No existe una API REST, GraphQL, SOAP ni un intercambio de JSON/XML. Las operaciones de escritura usan formularios `POST` y las respuestas son redirecciones o páginas HTML.

## 2. Arquitectura y archivos

```text
backend-node/
|-- package.json              Dependencias y comandos npm
|-- package-lock.json         Versiones concretas instaladas por npm
|-- schema.sql                Esquema relacional aplicado al iniciar
|-- INSTRUCTIONS.md           Este documento
|-- data/library.sqlite       Base SQLite local (se crea automaticamente)
|-- uploads/                  Portadas cargadas por los usuarios
`-- src/
    |-- server.js             Arranque, middleware, sesiones y servidor HTTP
    |-- db.js                 Conexion SQLite e inicializacion del esquema
    |-- routes.js             Rutas, control de acceso y acciones HTML
    |-- models/
    |   |-- userModel.js       Usuarios, autenticacion y contrasenas
    |   `-- catalogModel.js    Libros, autores, categorias, conceptos e imagenes
    |-- views/
    |   |-- home.ejs           Catalogo publico
    |   |-- login.ejs          Formulario de acceso
    |   |-- dashboard.ejs      Panel administrativo
    |   |-- error.ejs          Respuestas de error HTML
    |   `-- partials/           Cabecera y pie compartidos
    `-- public/app.css         Estilos publicos responsive
```

### `src/server.js`

- Crea el directorio `uploads`.
- Ejecuta `seedAdmin()` para crear una cuenta inicial solo si no existen usuarios.
- Configura EJS, formularios URL-encoded, archivos estaticos y sesiones.
- Expone el puerto definido por `PORT`, o el puerto `3000` por defecto.
- Comparte con las vistas el usuario conectado y los mensajes de una sola solicitud.
- Devuelve HTML para errores 404 y 500.

### `src/db.js`

- Usa `better-sqlite3`.
- Crea `data/library.sqlite` si no existe.
- Activa claves foraneas con `PRAGMA foreign_keys = ON`.
- Ejecuta `schema.sql` al arrancar; las sentencias son idempotentes porque usan `CREATE TABLE IF NOT EXISTS`.

### Modelos

`userModel.js` consulta la tabla `users`, compara contrasenas con `bcryptjs`, crea usuarios y administra sus roles.

`catalogModel.js` administra:

- `books`: titulo, ISBN, descripcion, precio en centimos, stock y ano.
- `authors`: nombre y biografia.
- `categories`: nombre y descripcion.
- `book_authors` y `book_categories`: relaciones muchos-a-muchos.
- `concepts`: termino y definicion asociada a un libro.
- `images`: nombre del archivo, nombre original, tipo MIME y libro relacionado.

Las eliminaciones de libros y entidades relacionadas respetan `ON DELETE CASCADE`. Las relaciones de un libro se sincronizan borrando las asociaciones anteriores y creando las seleccionadas en una transaccion SQLite.

### Rutas principales

- `GET /`: catalogo publico.
- `GET /login`: formulario de acceso.
- `POST /login`: autentica y crea la sesion.
- `POST /logout`: destruye la sesion.
- `GET /admin`: panel protegido.
- `POST /books` y `POST /books/:id/edit`: alta y actualizacion de libros.
- `POST /books/:id/delete`: baja de libros.
- `POST /authors`, `/categories`, `/concepts` y `/users`: altas.
- `POST /authors/:id/edit`, `/categories/:id/edit`, `/concepts/:id/edit` y `/users/:id/edit`: actualizaciones.
- Rutas `.../:id/delete`: bajas de entidades.
- `POST /images`: recibe una imagen multipart de hasta 5 MB.

Toda ruta administrativa usa `requireAuth`. La sesion guarda solamente `id`, `name` y `role`, nunca la contrasena.

## 3. Configuracion actual

El archivo `package.json` contiene los scripts:

```text
npm start    node src/server.js
npm run dev  node --watch src/server.js
```

Variables de entorno reconocidas:

| Variable | Obligatoria | Valor por defecto | Uso |
|---|---:|---|---|
| `PORT` | No | `3000` | Puerto HTTP de Node |
| `SESSION_SECRET` | Recomendado | Clave de ejemplo | Firma de la cookie de sesion |
| `ADMIN_EMAIL` | No | `admin@libreria.local` | Correo de la cuenta inicial |
| `ADMIN_PASSWORD` | No | `admin1234` | Contrasena de la cuenta inicial |

En produccion, define una clave aleatoria para `SESSION_SECRET` y una contrasena fuerte para el administrador. Las variables de administrador solo se usan al crear el primer usuario; cambiar el valor despues no modifica una cuenta ya existente.

Ejemplo PowerShell:

```powershell
$env:PORT="3000"
$env:SESSION_SECRET="genera-una-clave-larga-y-aleatoria"
$env:ADMIN_EMAIL="admin@tu-dominio.com"
$env:ADMIN_PASSWORD="una-clave-segura-de-8-o-mas-caracteres"
npm start
```

Ejemplo Linux:

```bash
export PORT=3000
export SESSION_SECRET='genera-una-clave-larga-y-aleatoria'
export ADMIN_EMAIL='admin@tu-dominio.com'
export ADMIN_PASSWORD='una-clave-segura-de-8-o-mas-caracteres'
npm start
```

## 4. Instalacion y visualizacion local

Requisito: Node.js 20 LTS o posterior.

### Windows 11

```powershell
cd C:\Temp\library\backend-node
npm install
npm start
```

Abrir en el navegador:

- Catalogo: `http://localhost:3000/`
- Acceso: `http://localhost:3000/login`
- Administracion: `http://localhost:3000/admin`

Para desarrollo con reinicio automatico, usar `npm run dev`. Detener con `Ctrl+C`.

### CentOS Stream 10

```bash
sudo dnf update -y
sudo dnf install -y curl gcc-c++ make python3
curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo bash -
sudo dnf install -y nodejs
cd /ruta/al/proyecto/backend-node
npm install
npm start
```

Desde el servidor: `http://localhost:3000/`.
Desde otro equipo: `http://IP_DEL_SERVIDOR:3000/`, despues de abrir el puerto:

```bash
sudo firewall-cmd --permanent --add-port=3000/tcp
sudo firewall-cmd --reload
```

Para produccion se recomienda colocar Nginx o un balanceador HTTPS delante de Node y ejecutar el proceso con systemd o un gestor de procesos.

## 5. Estado de la conexion a la base de datos real CGP/GCP

La version actual esta conectada a SQLite local, no a una base remota. La conexion se crea en `src/db.js` y no lee `DATABASE_URL`, `DB_HOST` ni otras variables de conexion. Por tanto, **no es correcto apuntar solamente una variable de entorno a la instancia remota**: los modelos tambien usan la API especifica de SQLite (`prepare`, `pragma` y `better-sqlite3`).

Antes de conectar una base real, confirmar estos datos de la instancia CGP/GCP:

- Proveedor exacto y nombre del servicio.
- Motor y version: SQLite, PostgreSQL, MySQL/MariaDB u otro.
- Host o IP, puerto y nombre de base de datos.
- Usuario, contrasena y certificado TLS/SSL.
- Red autorizada: VPC, VPN, IP del servidor Node o Cloud SQL Auth Proxy.
- Si la base es una copia de pruebas o produccion.

No guardar credenciales en `package.json`, `schema.sql`, el repositorio ni capturas de pantalla. Usar variables de entorno o un gestor de secretos.

### Opcion A: la instancia mantiene SQLite

Si CGP/GCP es una maquina virtual y la base real es SQLite, el archivo debe estar en el servidor donde corre Node. Copiar la base con la aplicacion y definir permisos para el usuario del proceso:

```bash
mkdir -p data uploads
cp /ruta/segura/library.sqlite data/library.sqlite
chmod 700 data uploads
chmod 600 data/library.sqlite
npm install
npm start
```

Hacer una copia de seguridad antes de reemplazar el archivo:

```bash
cp data/library.sqlite data/library.sqlite.$(date +%Y%m%d%H%M%S).bak
```

SQLite no debe compartirse simultaneamente desde varios servidores. Debe existir un solo proceso escritor o se debe migrar a un motor servidor.

### Opcion B: PostgreSQL, MySQL o MariaDB

Para una base servidor hay que realizar una adaptacion de persistencia antes del despliegue. El trabajo minimo es:

1. Crear un nuevo `src/db.js` usando el driver del motor elegido (`pg` para PostgreSQL o `mysql2` para MySQL/MariaDB).
2. Convertir las consultas de `catalogModel.js` y `userModel.js` al API del driver elegido; `db.prepare(...).get/all/run` no es portable.
3. Adaptar `schema.sql`: `AUTOINCREMENT`, tipos, restricciones, `group_concat` y placeholders cambian segun el motor.
4. Ejecutar el esquema en una base de pruebas y cargar datos de prueba.
5. Cambiar las consultas de agregacion de autores y categorias (`group_concat` es sintaxis SQLite; PostgreSQL suele usar `string_agg`, y MySQL `GROUP_CONCAT`).
6. Agregar un pool de conexiones, limites de tiempo, TLS y cierre ordenado del pool.
7. Usar migraciones versionadas en vez de aplicar cambios automaticamente al arrancar produccion.
8. Probar altas, actualizaciones, eliminaciones, relaciones, login y carga de imagenes contra una copia de la base real.

Una configuracion de entorno recomendada para un adaptador futuro es:

```text
DB_HOST=host-privado-o-proxy
DB_PORT=5432
DB_NAME=libreria
DB_USER=libreria_app
DB_PASSWORD=secreto-fuera-del-repositorio
DB_SSL=true
```

El puerto `5432` es un ejemplo de PostgreSQL; para MySQL/MariaDB normalmente es `3306`. No usar estos valores hasta confirmar el motor de la instancia.

### Red y acceso desde CGP/GCP

La aplicacion Node debe ejecutarse en una maquina que tenga ruta de red a la base. Abrir el puerto de la base solo para la IP privada del servidor de aplicacion o usar el mecanismo recomendado por el proveedor, como un proxy o conector administrado. No exponer el puerto de la base a `0.0.0.0/0`.

Si la base solo acepta conexiones privadas, desplegar Node en la misma VPC o conectar las redes mediante VPN. Validar conectividad desde el servidor con la herramienta del motor, por ejemplo `psql` para PostgreSQL o `mysql` para MySQL, antes de iniciar la aplicacion.

## 6. Orden recomendado para migrar datos

1. Crear una copia de seguridad de la base real.
2. Crear una base de pruebas con el mismo motor y version.
3. Traducir y ejecutar `schema.sql` en la base de pruebas.
4. Migrar primero `users`, sin reutilizar contrasenas en texto plano; las contrasenas deben ser hashes bcrypt.
5. Migrar autores, categorias, libros y despues las tablas de relacion.
6. Migrar conceptos e imagenes. Las imagenes no estan dentro de SQLite: copiar `uploads/` y conservar el nombre almacenado en `images.filename`.
7. Ejecutar pruebas manuales de login, catalogo, CRUD, relaciones y eliminacion en cascada.
8. Configurar el adaptador para pruebas y solo despues cambiar el secreto y las credenciales de produccion.
9. Programar copias de seguridad de la base y de `uploads/`.

## 7. Comprobacion previa al despliegue

```bash
node --version
npm install
npm start
```

Verificar:

- `GET /` devuelve el catalogo en HTML.
- Un usuario no autenticado que entra en `/admin` es redirigido a `/login`.
- El login correcto redirige a `/admin`.
- Crear un autor, categoria y libro conserva las relaciones.
- Una definicion queda asociada al libro correcto.
- Una portada se guarda en `uploads/` y se muestra en el catalogo.
- Eliminar un libro elimina sus relaciones y conceptos por cascada.
- `SESSION_SECRET` no usa el valor por defecto en produccion.
- La base y la carpeta de imagenes tienen copias de seguridad.

## 8. Nota de seguridad

La implementacion es un punto de partida funcional. Antes de exponerla a Internet conviene añadir proteccion CSRF para formularios, validacion mas estricta de entradas, limitacion de intentos de login, almacenamiento de sesiones persistente, cabeceras de seguridad, HTTPS y autorizacion por rol. En particular, `requireAuth` actualmente verifica que exista una sesion, pero no restringe acciones administrativas por el campo `role`.
