# Lumen Libros - Electron

Cliente de escritorio Electron para consultar el catálogo de libros de un microservicio que responde exclusivamente XML.

## Estado de la URL del microservicio

La URL del prompt se deja vacía intencionalmente. No hay una URL activa preconfigurada porque el home/endpoint definitivo será entregado posteriormente. La aplicación arranca mostrando el mensaje para configurar el servicio.

La dirección se configura desde el botón de engranaje. Se guardan la IP o dominio y el endpoint en `localStorage` del equipo. Ejemplo cuando se disponga de los datos definitivos:

```text
IP o dominio: 34.18.85.104:5001
Endpoint: /books
```

El cliente construye `http://34.18.85.104:5001/books`. También acepta que el campo de IP ya incluya `http://` o `https://`.

## Funcionalidades

- Aplicación de escritorio basada en Electron.
- Consulta del catálogo usando una petición al microservicio y respuesta XML.
- Rechazo de respuestas JSON, XML inválido y URLs incompletas.
- Tarjetas con foto, título, autores, ISBN y precio.
- Seis tarjetas por página al mostrar resultados.
- Paginación anterior/siguiente.
- Botón de actualización del catálogo.
- Modal para configurar IP/dominio y endpoint.
- Persistencia de la configuración mediante `localStorage`.
- Diseño responsive con tarjetas, colores, tipografía y componentes de estilo Material.
- `contextIsolation`, `sandbox` y `nodeIntegration: false` activados.
- La descarga se realiza mediante IPC en el proceso principal para evitar problemas de CORS de una página local.

## Estructura

```text
electron-app/
|-- package.json       Dependencias y comandos
|-- main.js            Proceso principal y ventana Electron
|-- preload.js         Puente seguro IPC hacia el renderer
|-- index.html         Estructura de la interfaz
|-- renderer.js        Estado, XML, tarjetas, modal y paginación
|-- styles.css         Diseño responsive
|-- .env.example       Referencia de configuración futura
`-- README.md          Esta guía
```

No es necesario crear un `.env` para esta versión. La configuración solicitada por el usuario se guarda en `localStorage`, no en archivos ni en el repositorio.

## Requisitos para Windows 11

1. Instala Node.js 20 LTS o una versión posterior desde [nodejs.org](https://nodejs.org/).
2. Comprueba la instalación en PowerShell:

```powershell
node --version
npm --version
```

3. Instala Git si vas a clonar el repositorio desde [git-scm.com](https://git-scm.com/).
4. Asegúrate de tener conectividad desde el equipo al host y puerto del microservicio.

## Descargar o abrir el proyecto

Si todavía no tienes el repositorio:

```powershell
cd C:\Temp
git clone https://github.com/VictorGtz0507/integracion1.git library
cd C:\Temp\library\apps\electron-app
```

Si ya tienes el proyecto descargado:

```powershell
cd C:\Temp\library\apps\electron-app
```

## Instalar y ejecutar en desarrollo

Instala las dependencias dentro de `electron-app`:

```powershell
npm install
```

Inicia la aplicación:

```powershell
npm start
```

También puedes usar:

```powershell
npm run dev
```

Se abrirá una ventana de escritorio. Presiona el botón de configuración, escribe la IP y el endpoint reales, guarda y pulsa `↻ Actualizar`.

## Formato XML esperado

El parser reconoce elementos `book`, `libro` o `item` y estos nombres de campos:

```xml
<books>
  <book>
    <title>El nombre del libro</title>
    <authors>Nombre del autor</authors>
    <isbn>9780000000000</isbn>
    <price>19.95 EUR</price>
    <image>https://servidor.example/portada.jpg</image>
  </book>
</books>
```

También reconoce equivalentes en español como `titulo`, `autores`, `autor`, `precio`, `foto`, `imagen`, `portada` e `isbn`. La etiqueta de imagen debe ser una URL accesible por el equipo.

## Probar la conexión

Antes de usar la aplicación, verifica desde PowerShell que el endpoint devuelve XML:

```powershell
Invoke-WebRequest -Uri "http://HOST:PUERTO/ENDPOINT" -Headers @{ Accept = "application/xml" }
```

La respuesta debe comenzar con una estructura XML, por ejemplo `<books>`. Si el servicio devuelve JSON, la aplicación lo rechazará deliberadamente.

## Empaquetar un instalador

Después de instalar las dependencias, ejecuta:

```powershell
npm run dist
```

`electron-builder` generará los artefactos de distribución en la carpeta `dist`. Es posible que Windows muestre advertencias de firma porque el instalador no tiene todavía un certificado de firma de código.

## Solución de problemas

- **No aparece ningún libro:** abre Configuración y confirma IP, protocolo y endpoint.
- **HTTP 404:** el endpoint no es correcto; solicita la ruta real del microservicio.
- **Respuesta JSON:** el servicio no cumple el contrato XML requerido.
- **XML inválido:** revisa caracteres especiales y etiquetas sin cerrar.
- **No cargan las fotos:** comprueba que la URL de cada imagen sea accesible y que el servidor permita el recurso.
- **El puerto no responde:** verifica firewall, red de la VM y que el microservicio esté iniciado.
- **Error al instalar `better-sqlite3`:** no aplica a esta aplicación; Electron solo necesita las dependencias definidas en este `package.json`.

## Comandos resumidos

```powershell
cd C:\Temp\library\apps\electron-app
npm install
npm start
```
