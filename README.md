# Fernando Luna Backend

API Python para alimentar el portal personal.

Todo el contenido del portal (perfil, secciones, items, pestañas e items de pestaña)
vive en PostgreSQL y se edita desde el panel de administración. Sin `FERLUNA_DATABASE_URL`,
la API sirve el contenido de seed local como fallback de desarrollo.

## Instalar dependencias opcionales

```powershell
python -m pip install -r requirements.txt
```

## Ejecutar

```powershell
python -m app.main
```

Variables opcionales:

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

## PostgreSQL

Crear tablas (idempotente):

```powershell
python -m app.main init-db
```

Cargar el contenido inicial editable:

```powershell
python -m app.main seed-db
```

`seed-db` es destructivo: reemplaza todo el contenido por el seed. Ejecútalo solo
en una base vacía o cuando quieras restablecer el contenido por defecto.

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
