# Redis / PostgreSQL Benchmark

Aplicación independiente que compara lecturas del catálogo PostgreSQL del proyecto contra una copia JSON temporal en Redis. Mide lecturas directas, aciertos de caché y la ruta de caché fría (lectura PostgreSQL más escritura Redis). Presenta tamaño total de la base, memoria de la instancia Redis y bytes del catálogo serializado.

## Alcance y precauciones

- Solo lee tablas; no modifica libros ni esquemas.
- Usa las tablas PostgreSQL `books`, `authors`, `book_authors`, `categories`, `book_categories`, `concepts` e `images`, con columnas compatibles con `apps/services/soap/app.py`.
- Redis contiene exclusivamente una clave con prefijo configurable, con vencimiento; la acción «Vaciar caché» elimina únicamente esa clave.
- PostgreSQL y Redis no almacenan exactamente el mismo tipo de estructura. `pg_database_size` incluye tablas e índices de toda la base; `used_memory` mide toda la instancia Redis, y los bytes JSON no incluyen overhead de Redis. Son indicadores útiles, no tamaños directamente equivalentes.
- La prueba es secuencial y corre desde el servidor Flask en que se ejecuta. No es un benchmark de concurrencia ni de red distribuida.
- Se comparan todas las filas de `books`. El tiempo y la memoria crecerán con el catálogo; empieza con 10 repeticiones.
- La velocidad Redis mide GET más parseo JSON en el proceso. El acierto de caché se precalienta antes de medir. La ruta de caché fría borra y repuebla solo la clave del benchmark.

## Requisitos

- Python 3.10 o posterior.
- PostgreSQL accesible con un esquema de catálogo existente. La app usa Psycopg 3, como el servicio de login del proyecto.
- Redis accesible desde el equipo donde corre esta app. En Windows se puede usar Docker Desktop; en CentOS Stream 10, Docker/Podman o una instancia Redis privada.

## Windows 11

En PowerShell, abre dos terminales. En la primera inicia Redis con Docker:

```powershell
cd C:\Temp\library\apps\redis-postgres-benchmark
# Asegúrate de que Docker Desktop esté iniciado.
docker compose up -d redis
```

En la segunda configura Python y PostgreSQL:

```powershell
cd C:\Temp\library\apps\redis-postgres-benchmark
Copy-Item .env.example .env
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Edita `.env` para que `DB_HOST`, usuario, contraseña y puerto correspondan a la instancia PostgreSQL visible desde esta máquina. `localhost` solo sirve si PostgreSQL corre en la misma VM. Luego arranca:

```powershell
python app.py
```

Abre <http://127.0.0.1:5050>.

## CentOS Stream 10

Ejemplo con Docker Compose Plugin instalado:

```bash
cd /ruta/al/proyecto/apps/redis-postgres-benchmark
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
docker compose up -d redis
```

Edita `.env`, en especial `DB_HOST` y `REDIS_URL`. Para abrir el dashboard desde otra máquina, define `APP_HOST=0.0.0.0`, restringe el firewall a tu red y usa un proxy HTTPS para un entorno no local. Redis no debe exponerse públicamente. Arranca en otra terminal:

```bash
source .venv/bin/activate
python app.py
```

Abre `http://IP_DE_LA_VM:5050`. Para detener Redis: `docker compose down`.

## Variables

Se puede configurar PostgreSQL con `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, o con `DATABASE_URL`. Redis usa `REDIS_URL`, por ejemplo `redis://localhost:6379/0`. `REDIS_CATALOG_KEY` permite cambiar la clave aislada de caché y `CACHE_TTL_SECONDS` su vencimiento (300 segundos por defecto).

Usa credenciales de base de datos con permisos de solo lectura. No compartas ni publiques `.env`.

## Cómo ejecutar y leer una prueba

1. Verifica que los indicadores de PostgreSQL y Redis muestren «Conectado».
2. Selecciona 10 repeticiones y ejecuta la prueba.
3. Compara medianas y P95; la velocidad varía según caché del sistema operativo, red, tamaño del catálogo y carga de la VM.
4. Comprueba que «Las dos rutas devolvieron los mismos libros» aparezca como resultado.
5. Revisa tamaños: base de datos completa en PostgreSQL, memoria de Redis y bytes JSON propios del catálogo.

El indicador de «veces más rápido» es mediana PostgreSQL / mediana Redis. Un resultado mayor que 1 indica que el acierto de caché fue más rápido en esa corrida; no significa que Redis reemplace la capacidad de consulta, persistencia o consistencia de PostgreSQL.

## Pruebas locales

Con el entorno virtual activo:

```powershell
python -m unittest discover -s tests
```