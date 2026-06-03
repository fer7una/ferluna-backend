# Fernando Luna Backend

API Python para alimentar el portal personal.

Todo el contenido del portal (perfil, secciones, items, pestañas e items de pestaña)
vive en PostgreSQL y se edita desde el panel de administración. Sin `FERLUNA_DATABASE_URL`,
la API sirve el contenido de seed local como fallback de desarrollo.

## Instalar dependencias

```powershell
python -m pip install -r requirements.txt
```

## Variables de entorno

Configura las variables en `ferluna-backend/.env`. El backend carga ese fichero
automáticamente al ejecutar `python -m app.main`, `python -m app.main init-db` y
`python -m app.main seed-db`.

Las variables ya definidas en el sistema tienen prioridad sobre `.env`, así que
puedes sobrescribir valores puntualmente desde la terminal si lo necesitas.

Configura solo las que necesites para el modo de arranque elegido:

```env
FERLUNA_API_HOST=127.0.0.1
FERLUNA_API_PORT=8000
FERLUNA_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
FERLUNA_DATABASE_URL=postgresql://usuario:password@localhost:5432/ferluna
FERLUNA_ADMIN_PASSWORD=change-me
FERLUNA_JWT_SECRET=use-a-long-random-secret
FERLUNA_JWT_TTL_SECONDS=1800
FERLUNA_LOGIN_RATE_LIMIT=10
FERLUNA_LOGIN_RATE_WINDOW=300
```

`FERLUNA_LOGIN_RATE_LIMIT` limita los intentos de login por IP dentro de
`FERLUNA_LOGIN_RATE_WINDOW` segundos (usa `0` para desactivar el límite).

## Maneras de iniciar el backend

El backend puede quedarse en tres estados útiles: API de lectura sin BD, API
levantada pero con BD incompleta, o backend completo.

### 1. API sola, sin PostgreSQL

Arranca solo el servidor HTTP:

```powershell
cd ferluna-backend
python -m app.main
```

Qué se inicia:

- `GET /api/health` responde `ok`.
- `GET /api/site` sirve el seed local de desarrollo.

Cómo se queda a medias:

- No hay persistencia real: los cambios no se guardan en PostgreSQL.
- El panel admin no puede guardar contenido porque falta `FERLUNA_DATABASE_URL`.
- Si configuras `FERLUNA_ADMIN_PASSWORD` y `FERLUNA_JWT_SECRET`, el login puede emitir
  JWT, pero `PUT /api/admin/site` seguirá devolviendo `database_disabled`.

Úsalo solo para ver la API pública con contenido de fallback.

### 2. API con PostgreSQL arrancado, pero sin esquema o sin seed

Primero levanta PostgreSQL. Si no tienes una instancia local, puedes usar Docker:

```powershell
docker run --name ferluna-postgres `
  -e POSTGRES_USER=ferluna `
  -e POSTGRES_PASSWORD=ferluna `
  -e POSTGRES_DB=ferluna `
  -p 5432:5432 `
  -d postgres:16
```

Si el contenedor ya existe y está parado:

```powershell
docker start ferluna-postgres
```

Después configura la conexión en `ferluna-backend/.env`:

```env
FERLUNA_DATABASE_URL=postgresql://ferluna:ferluna@localhost:5432/ferluna
```

Cómo se queda a medias:

- Si PostgreSQL no está realmente escuchando en `localhost:5432`, el servidor puede arrancar, pero `/api/site` fallará al intentar conectar.
- Si la BD existe pero todavía no ejecutaste `init-db`, faltan las tablas y las rutas que leen contenido fallarán.
- Si ejecutaste `init-db` pero no `seed-db`, el esquema existe y la API puede leer la BD, pero el contenido editable queda prácticamente vacío: perfil de fallback, colecciones vacías y `revision` en `0`.

Este estado sirve para comprobar conexión y esquema, no para usar el portal completo.

### 3. Backend completo

Secuencia completa de arranque local:

```powershell
cd ferluna-backend
python -m pip install -r requirements.txt

python -m app.main init-db
python -m app.main seed-db
python -m app.main
```

Qué se inicia, en orden:

1. PostgreSQL queda escuchando en `localhost:5432`.
2. `.env` aporta `FERLUNA_DATABASE_URL` para usar PostgreSQL en vez del seed local.
3. `init-db` crea o actualiza las tablas de forma idempotente.
4. `seed-db` carga el contenido inicial editable.
5. `.env` aporta `FERLUNA_ADMIN_PASSWORD` y `FERLUNA_JWT_SECRET` para activar el login admin.
6. `python -m app.main` inicia el servidor HTTP en `http://127.0.0.1:8000` y se queda ejecutándose en esa terminal.

Así queda completamente arrancado:

- `GET /api/health` responde `ok`.
- `GET /api/site` lee contenido desde PostgreSQL.
- `POST /api/admin/login` devuelve un JWT si la contraseña coincide.
- `GET /api/admin/site` devuelve el documento editable con `revision`.
- `PUT /api/admin/site` guarda cambios en la BD si envías `expectedRevision` correcto.

`seed-db` es destructivo: reemplaza todo el contenido por el seed. Ejecútalo solo en
una base vacía o cuando quieras restablecer el contenido por defecto.

## Comandos de mantenimiento de PostgreSQL

Crear tablas (idempotente):

```powershell
python -m app.main init-db
```

Cargar el contenido inicial editable:

```powershell
python -m app.main seed-db
```

## Endpoints

- `GET /api/health`
- `GET /api/site` — payload público (`profile`, `sections`, `sectionItems`, `momentaryTabs`, `momentaryItems`)
- `POST /api/admin/login`
- `GET /api/admin/site`
- `PUT /api/admin/site`

`POST /api/admin/login` recibe `{ "password": "..." }` y devuelve un JWT con expiración.
Las rutas `/api/admin/site` requieren `Authorization: Bearer <jwt>`.

`GET /api/admin/site` devuelve el documento editable completo más `revision`.
`PUT /api/admin/site` reemplaza todo el contenido; envía `expectedRevision` (la última
`revision` cargada) para detectar ediciones concurrentes: si no coincide responde `409`.

## Tests

```powershell
python -m unittest discover -s tests
```
