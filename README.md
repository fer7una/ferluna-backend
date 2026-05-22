# Fernando Luna Backend

API Python sin dependencias externas para alimentar el portal personal.

## Ejecutar

```powershell
python -m app.main
```

Variables opcionales:

```env
FERLUNA_API_HOST=127.0.0.1
FERLUNA_API_PORT=8000
FERLUNA_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

## Endpoints

- `GET /api/health`
- `GET /api/profile`
- `GET /api/cv`
- `GET /api/projects`
- `GET /api/posts`
- `GET /api/docs`
- `GET /api/site`

## Tests

```powershell
python -m unittest discover -s tests
```
