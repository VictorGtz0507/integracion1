# Lumen / Librería monolítica

Aplicación web monolítica MVC para administrar una librería online. Node.js procesa formularios HTML, consulta SQLite directamente y renderiza HTML con EJS. No expone APIs REST, GraphQL, SOAP ni intercambia JSON/XML.

## Qué se implementó

- Servidor Node.js en un único proceso con arquitectura monolítica y organización modular.
- Patrón MVC: modelos para persistencia, rutas/controladores para las acciones y vistas EJS para renderizar HTML en el servidor.
- Base de datos SQLite creada automáticamente desde `schema.sql`, con claves foráneas y tablas para usuarios, libros, autores, categorías, relaciones, conceptos e imágenes.
- Catálogo público con título, autoría, categorías, descripción, precio, stock y portada.
- Acceso privado mediante sesiones y contraseñas cifradas con `bcryptjs`.
- Panel de administración para registrar y eliminar usuarios, crear y actualizar entidades del catálogo, gestionar definiciones asociadas a libros y subir o eliminar imágenes.
- Carga de portadas limitada a archivos de imagen de hasta 5 MB.
- Interfaz HTML responsive para escritorio y dispositivos móviles.
- Persistencia local en `backend-node/data/library.sqlite` y almacenamiento de imágenes en `backend-node/uploads`.

Todas las operaciones se realizan mediante formularios HTML y respuestas HTML del servidor. No se implementaron endpoints de servicios ni intercambio de datos JSON/XML.

## Estructura

- `backend-node/src/models`: acceso directo a SQLite y reglas de persistencia.
- `backend-node/src/routes.js`: controladores HTTP/formularios del monolito.
- `backend-node/src/views`: vistas EJS renderizadas en el servidor.
- `backend-node/src/public`: estilos y recursos públicos.
- `backend-node/schema.sql`: esquema normalizado, creado automáticamente.
- `backend-node/data`: base SQLite local generada al primer arranque.
- `backend-node/uploads`: imágenes subidas, excluidas del código fuente.

## Windows 11

1. Instala Node.js 20 LTS o superior desde https://nodejs.org/ y abre PowerShell.
2. Entra al proyecto: `cd C:\Temp\library\backend-node`
3. Instala dependencias: `npm install`
4. Arranca: `npm start`
5. Abre `http://localhost:3000`.

### Visualizar la aplicación en Windows

1. Mantén abierta la ventana de PowerShell mientras el servidor esté funcionando.
2. En un navegador, visita [http://localhost:3000](http://localhost:3000) para visualizar el catálogo público.
3. Para administrar la librería, visita [http://localhost:3000/login](http://localhost:3000/login) e inicia sesión.
4. Después del acceso, el panel de gestión estará disponible en [http://localhost:3000/admin](http://localhost:3000/admin).
5. Para detener la aplicación, vuelve a PowerShell y presiona `Ctrl+C`.

La cuenta inicial es `admin@libreria.local` con contraseña `admin1234`. Cámbiala creando otra cuenta y eliminando la inicial. Para personalizarla antes del primer arranque:

```powershell
$env:ADMIN_EMAIL="admin@mi-dominio.local"
$env:ADMIN_PASSWORD="una-clave-de-8-o-mas-caracteres"
$env:SESSION_SECRET="otra-clave-larga-y-aleatoria"
npm start
```

## CentOS Stream 10

```bash
sudo dnf update -y
sudo dnf install -y curl gcc-c++ make python3
curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo bash -
sudo dnf install -y nodejs
cd /ruta/al/proyecto/backend-node
npm install
export ADMIN_EMAIL='admin@mi-dominio.local'
export ADMIN_PASSWORD='una-clave-de-8-o-mas-caracteres'
export SESSION_SECRET='otra-clave-larga-y-aleatoria'
npm start
```

Después visita `http://IP_DEL_SERVIDOR:3000`. Para uso en red, permite el puerto con `sudo firewall-cmd --permanent --add-port=3000/tcp && sudo firewall-cmd --reload` y usa un proxy HTTPS (por ejemplo Nginx) delante de Node. Conserva las carpetas `data` y `uploads` en las copias de seguridad.

### Visualizar la aplicación en CentOS

Desde el mismo servidor puedes abrir `http://localhost:3000`. Desde otro equipo de la red, abre `http://IP_DEL_SERVIDOR:3000` en el navegador. El catálogo público se muestra en `/` y el panel privado en `/login` y `/admin`.

## Desarrollo

`npm run dev` reinicia el servidor cuando cambia el código. El esquema se aplica automáticamente y las claves foráneas están activadas.
