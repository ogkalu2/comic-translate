# API Reorganization Guide

## Overview

All FastAPI backend code has been reorganized into a dedicated `fast-api/` folder to separate API concerns from the desktop application. This improves:

- **Code organization**: Clear separation between GUI and API
- **Maintainability**: Easier to find and modify API-specific code
- **Contribution**: Cleaner structure for open-source contributions
- **Deployment**: API can be deployed independently

## What Changed

### New Structure

```
fast-api/
├── __init__.py
├── README.md                      # FastAPI-specific documentation
├── run_server.py                  # Server startup script
├── app/
│   ├── __init__.py
│   ├── main.py                   # FastAPI application
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py             # All API endpoints
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py            # Pydantic models
│   └── services/
│       ├── __init__.py
│       └── manga_service.py      # Business logic
└── scripts/
    ├── download_models.py         # Model download utility
    └── test_client.py             # API test client
```

### File Migrations

| Old Location | New Location | Status |
|-------------|--------------|--------|
| `server.py` | `fast-api/app/main.py` + `fast-api/app/api/routes.py` | Deprecated |
| `run_server.py` | `fast-api/run_server.py` | Deprecated |
| `download_models.py` | `fast-api/scripts/download_models.py` | Deprecated |
| `test_client.py` | `fast-api/scripts/test_client.py` | Deprecated |
| `services/manga_service.py` | `fast-api/app/services/manga_service.py` | Deprecated |
| `models/schemas.py` | `fast-api/app/models/schemas.py` | Deprecated |

**Note**: Old files are kept for backward compatibility but will be removed in a future version.

## Migration Guide

### For Users

If you were using the old commands:

**Old:**
```bash
python run_server.py
python download_models.py
python test_client.py manga.jpg
```

**New:**
```bash
python fast-api/run_server.py
python fast-api/scripts/download_models.py
python fast-api/scripts/test_client.py manga.jpg
```

### For Developers

If you have code importing from the old locations:

**Old imports:**
```python
from services.manga_service import MangaTranslationService
from models.schemas import DetectionResponse
```

**New imports:**
```python
from fast_api.app.services.manga_service import MangaTranslationService
from fast_api.app.models.schemas import DetectionResponse
```

### Environment Configuration

No changes needed. The API still uses the same `config/settings.py` and `.env` file.

## Benefits

1. **Clear Separation**: Desktop app (`app/`) and API (`fast-api/`) are now clearly separated
2. **Modular Design**: Each component has a specific purpose and location
3. **Independent Development**: API and GUI can be developed independently
4. **Better Documentation**: Each folder has its own README
5. **Easier Deployment**: API can be containerized and deployed separately

## Running the API

### Development

```bash
# From project root
python fast-api/run_server.py

# With uv
uv run python fast-api/run_server.py
```

### Production

```bash
# Using uvicorn directly
uvicorn fast_api.app.main:app --host 0.0.0.0 --port 8000

# With multiple workers
uvicorn fast_api.app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## Testing

### Using the test client

```bash
python fast-api/scripts/test_client.py path/to/manga.jpg
```

### Using curl

```bash
curl -X POST "http://localhost:8000/api/v1/translate" \
  -F "file=@manga.jpg" \
  -F "source_lang=Japanese" \
  -F "target_lang=English"
```

### Interactive documentation

Visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Contributing

When contributing API-related code:

1. **Routes**: Add new endpoints in `fast-api/app/api/routes.py`
2. **Models**: Define schemas in `fast-api/app/models/schemas.py`
3. **Business Logic**: Implement in `fast-api/app/services/`
4. **Scripts**: Add utilities in `fast-api/scripts/`
5. **Tests**: Add tests for new functionality
6. **Documentation**: Update `fast-api/README.md` and `API_README.md`

## Future Plans

- Remove deprecated files in the project root
- Add comprehensive test suite for API
- Add Docker support for easy deployment
- Add API versioning support
- Add rate limiting and authentication options

## Questions?

- Check `fast-api/README.md` for FastAPI-specific documentation
- Check `API_README.md` for complete API documentation
- Check `QUICKSTART.md` for quick start guide
