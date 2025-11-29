# FastAPI Backend for Comic Translate

This folder contains the FastAPI backend server that exposes the manga translation functionality as a REST API.

## Structure

```
fast-api/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application entry point
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py        # API route definitions
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py       # Pydantic models for requests/responses
│   └── services/
│       ├── __init__.py
│       └── manga_service.py # Business logic for translation operations
├── scripts/
│   ├── download_models.py   # Script to pre-download models
│   └── test_client.py       # Example client for testing the API
├── run_server.py            # Server startup script
└── README.md               # This file
```

## Quick Start

### 1. Start the Server

From the project root directory:

```bash
# Using Python directly
python fast-api/run_server.py

# Or using uv (recommended)
uv run python fast-api/run_server.py
```

The server will start on `http://localhost:8000`

### 2. Download Models (Optional)

Pre-download models for faster first requests:

```bash
# In another terminal, with the server running
python fast-api/scripts/download_models.py
```

### 3. Test the API

```bash
# Using the test client
python fast-api/scripts/test_client.py path/to/manga_image.jpg

# Or using curl
curl -X POST "http://localhost:8000/api/v1/translate" \
  -F "file=@manga_page.jpg" \
  -F "source_lang=Japanese" \
  -F "target_lang=English"
```

## API Documentation

Once the server is running, visit:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

For detailed API documentation, see the main [API_README.md](../API_README.md) in the project root.

## Key Endpoints

- `GET /health` - Health check
- `POST /api/v1/detection` - Detect text blocks
- `POST /api/v1/ocr` - Perform OCR
- `POST /api/v1/translation` - Translate text
- `POST /api/v1/inpainting` - Remove text from image
- `POST /api/v1/translate` - Full translation pipeline
- `GET /api/v1/models` - List available models
- `POST /api/v1/models/download` - Download models

## Configuration

Server configuration is managed through `config/settings.py` in the project root. You can customize:

- Host and port
- Default models
- GPU acceleration
- Language settings

Create a `.env` file in the project root to override defaults:

```env
HOST=0.0.0.0
PORT=8000
ENABLE_GPU=False
DEFAULT_DETECTOR=RT-DETR-V2
DEFAULT_OCR=Default
DEFAULT_TRANSLATOR=Google Translate
DEFAULT_INPAINTER=LaMa
```

## Development

The FastAPI backend is designed to be:

- **Modular**: Separate concerns (routes, services, models)
- **Testable**: Business logic isolated from API layer
- **Extensible**: Easy to add new endpoints or models
- **Production-ready**: Proper error handling, logging, and validation

## Contributing

When contributing to the API:

1. Add new routes in `app/api/routes.py`
2. Define schemas in `app/models/schemas.py`
3. Implement business logic in `app/services/`
4. Update API documentation
5. Add tests for new functionality

## Notes

- All API-related code is now isolated in this folder
- The main application (`app/`, `modules/`, etc.) remains focused on the desktop GUI
- Both the API and GUI share the same core translation modules
- Models are cached and shared across requests for performance
