# Fernando Luna Backend

API Python para alimentar el portal personal.

El contenido editable puede vivir en PostgreSQL. Sin `FERLUNA_DATABASE_URL`, la API usa el contenido local de fallback.

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
```

## PostgreSQL

Crear tablas:

```powershell
python -m app.main init-db
```

Cargar el contenido inicial editable:

```powershell
python -m app.main seed-db
```

## Endpoints

- `GET /api/health`
- `GET /api/profile`
- `GET /api/cv`
- `GET /api/projects`
- `GET /api/posts`
- `GET /api/docs`
- `GET /api/site`
- `POST /api/admin/login`
- `GET /api/admin/site`
- `PUT /api/admin/site`

`POST /api/admin/login` recibe `{ "password": "..." }` y devuelve un JWT con expiracion. Las rutas `/api/admin/site` requieren `Authorization: Bearer <jwt>`.

## Tests

```powershell
python -m unittest discover -s tests
```
