# Credentials Guide

## Overview

The backend server now supports API credentials for services that require authentication (like Google Cloud Vision, Microsoft Azure OCR, DeepL, GPT-4, etc.).

## Current Status

**Fixed Issue**: The `MockSettingsPage` class now includes the `get_credentials()` method required by OCR and translation factories. By default, it returns empty credentials.

## How Credentials Work

### Default Behavior (No Credentials)

Most OCR and translation engines work without credentials:
- **Manga OCR** - No credentials needed
- **PPOCRv5** - No credentials needed  
- **Pororo OCR** - No credentials needed
- **Google Translate** - No credentials needed (uses free API)

### Services Requiring Credentials

Some services require API keys:
- **Microsoft Azure OCR** - Requires `api_key_ocr`, `endpoint`, `region_translator`
- **Google Cloud Vision OCR** - Requires `api_key`
- **DeepL Translation** - Requires `api_key`
- **GPT-4 OCR/Translation** - Requires `api_key`, optional `api_url`, `model`
- **Gemini OCR/Translation** - Requires `api_key`
- **Microsoft Azure Translation** - Requires `api_key_translator`, `region_translator`
- **Yandex Translation** - Requires `api_key`, `folder_id`

## Adding Credentials Support (Future Enhancement)

### Option 1: Environment Variables (Recommended)

Add credentials via environment variables in `config/settings.py`:

```python
class Settings(BaseSettings):
    # ... existing settings ...
    
    # API Credentials
    microsoft_azure_api_key: str = ""
    microsoft_azure_endpoint: str = ""
    microsoft_azure_region: str = ""
    google_cloud_api_key: str = ""
    deepl_api_key: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = ""
    
    model_config = SettingsConfig(
        env_file=".env",
        env_prefix="MANGA_"
    )
```

Then create a `.env` file:
```
MANGA_MICROSOFT_AZURE_API_KEY=your_key_here
MANGA_GOOGLE_CLOUD_API_KEY=your_key_here
```

### Option 2: API Request Parameters

Add credentials as optional parameters to API endpoints:

```python
@app.post("/api/v1/ocr")
async def perform_ocr(
    file: UploadFile = File(...),
    source_lang: str = Form("Japanese"),
    ocr_model: str = Form("Default"),
    # Add credential fields
    api_key: Optional[str] = Form(None, description="API key for cloud OCR services"),
    api_endpoint: Optional[str] = Form(None, description="API endpoint for Azure OCR"),
    api_region: Optional[str] = Form(None, description="API region for Azure services")
):
    # Build credentials dict
    credentials = {}
    if api_key:
        credentials = {
            'api_key': api_key,
            'endpoint': api_endpoint,
            'region': api_region
        }
    
    # Pass to service
    result = manga_service.perform_ocr(
        image=image,
        source_lang=source_lang,
        ocr_model=ocr_model,
        credentials=credentials  # New parameter
    )
```

### Option 3: Dedicated Credentials Endpoint

Create an endpoint to store credentials temporarily:

```python
from pydantic import BaseModel

class ServiceCredentials(BaseModel):
    service: str  # "Microsoft Azure", "Google Cloud", etc.
    api_key: Optional[str] = None
    api_url: Optional[str] = None
    region: Optional[str] = None
    endpoint: Optional[str] = None

# In-memory storage (or use database)
credentials_store: Dict[str, Dict[str, str]] = {}

@app.post("/api/v1/credentials")
async def set_credentials(creds: ServiceCredentials):
    """Store credentials for a service."""
    credentials_store[creds.service] = creds.model_dump(exclude={'service'}, exclude_none=True)
    return {"message": f"Credentials set for {creds.service}"}

@app.delete("/api/v1/credentials/{service}")
async def delete_credentials(service: str):
    """Delete credentials for a service."""
    if service in credentials_store:
        del credentials_store[service]
        return {"message": f"Credentials deleted for {service}"}
    raise HTTPException(status_code=404, detail="Service not found")
```

Then update `MangaTranslationService` to use the stored credentials:

```python
class MangaTranslationService:
    def __init__(self, credentials_store: Optional[Dict[str, Dict[str, str]]] = None):
        self.credentials_store = credentials_store or {}
        # ... rest of init ...
    
    def perform_ocr(self, ..., credentials: Optional[Dict[str, str]] = None):
        # Merge provided credentials with stored credentials
        all_credentials = {**self.credentials_store, **(credentials or {})}
        
        settings = MockSettingsPage(
            ocr_model=ocr_model,
            use_gpu=use_gpu,
            credentials=all_credentials  # Pass credentials
        )
        # ... rest of method ...
```

## Implementation Steps

To add full credentials support:

1. **Update `config/settings.py`** - Add credential fields
2. **Update `services/manga_service.py`** - Accept credentials parameter in all methods
3. **Update `server.py`** - Pass credentials from config or request to service methods
4. **Update API schemas in `models/schemas.py`** - Add credential fields (optional)
5. **Update documentation** - Explain how to use credentials

## Security Considerations

⚠️ **Important**: When implementing credential support:

1. **Never log credentials** - Ensure API keys are not written to logs
2. **Use HTTPS** - Always use HTTPS in production to encrypt credentials in transit
3. **Environment variables** - Prefer environment variables over request parameters
4. **Credential storage** - If storing credentials, use encryption at rest
5. **Rate limiting** - Implement rate limiting to prevent API key abuse
6. **API key rotation** - Support updating credentials without restarting the server

## Testing with Credentials

Example using Google Cloud Vision OCR with credentials (once implemented):

```python
import requests

# Set credentials (Option 3)
requests.post("http://localhost:8000/api/v1/credentials", json={
    "service": "Google Cloud",
    "api_key": "your_google_cloud_api_key"
})

# Use OCR
with open("manga_page.jpg", "rb") as f:
    response = requests.post(
        "http://localhost:8000/api/v1/ocr",
        files={"file": f},
        data={
            "source_lang": "Japanese",
            "ocr_model": "Google Cloud Vision"
        }
    )

print(response.json())
```

## Current Workaround

Until credentials support is fully implemented, you can:

1. Use **free services** that don't require credentials:
   - Manga OCR (default for Japanese)
   - PPOCRv5 (supports multiple languages)
   - Google Translate (for translation)

2. **Modify the service layer directly** by hardcoding credentials in `services/manga_service.py`:

```python
settings = MockSettingsPage(
    ocr_model=ocr_model,
    use_gpu=use_gpu,
    credentials={
        "Google Cloud": {"api_key": "your_key_here"},
        "Microsoft Azure": {
            "api_key_ocr": "your_key",
            "endpoint": "your_endpoint",
            "region": "your_region"
        }
    }
)
```

## Summary

- ✅ Basic credential infrastructure is in place
- ✅ `MockSettingsPage.get_credentials()` method implemented
- ⏳ Full credential passing from API to services - Not yet implemented
- ⏳ Credential storage/management - Not yet implemented

The system is ready for credential support - it just needs the plumbing to pass credentials from the API level down to the service layer.
