# Lumen Libros - Electron

Cliente de escritorio Electron para consultar el catálogo y abrir los seis microservicios de Library.

## Microservicios y configuración

La barra superior tiene un botón por servicio. Al pulsarlo, abre esa URL en el navegador del sistema. Los indicadores consultan `/health` cada 15 segundos: verde significa HTTP 200, amarillo que el servicio respondió con otro código HTTP (por ejemplo, degradado), y rojo que no se pudo conectar.

El engrane permite modificar las seis URL base y la ruta del catálogo. Los valores locales son:

```text
Login:   http://localhost:5000
Books:   http://localhost:5001
Users:   http://localhost:5002
Authors: http://localhost:5003
Pedidos: http://localhost:5004
Pagos:   http://localhost:5005
```

Usa HTTP para los servicios Flask locales, que no tienen TLS habilitado. Para acceder a una VM, sustituye `localhost` por su IP o dominio. En producción configura HTTPS en un proxy TLS y guarda las URL `https://` correspondientes. El catálogo se consulta por defecto desde Books en `/api/books`; se aceptan respuestas JSON y XML.

## Funcionalidades

- Aplicación de escritorio basada en Electron.
- Consulta del catálogo mediante JSON o XML.
- Seis botones de navegación con estado de conexión.
- Comprobación periódica de salud mediante `/health`.
- Configuración editable de las seis URL y la ruta del catálogo.
- Validación de enlaces HTTP/HTTPS.
- Tarjetas con foto, título, autores, ISBN y precio.
- Seis tarjetas por página al mostrar resultados.
- Paginación anterior/siguiente.
- Botón de actualización del catálogo.
- Modal para configurar los microservicios.
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
|-- services.css      Barra de microservicios y semáforos
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

Se abrirá una ventana de escritorio. En Configuración puedes cambiar las URL; al usar una VM, reemplaza `localhost` por la IP alcanzable de esa VM.

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
- **Catálogo sin libros:** confirma que Books devuelve JSON con una lista en `/api/books` o XML compatible en la ruta configurada.
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
