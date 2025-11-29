# Quick Start Guide - Manga Translation API Server

This guide will help you quickly set up and run the Manga Translation API backend server.

## Installation (5 minutes)

### Step 1: Install Dependencies

**Recommended - Using UV (Fast!):**
```bash
uv sync
```

**Alternative - Using pip:**
```bash
# Full installation (with GUI support)
pip install -r requirements.txt

# Or server only (headless, no GUI)
pip install -r requirements-server.txt
```

### Step 2: Configure Settings (Optional)

Copy the example environment file:
```bash
copy .env.example .env
```

Edit `.env` to customize settings:
- Change `PORT` if 8000 is already in use
- Set `ENABLE_GPU=True` if you have a CUDA-compatible GPU
- Adjust default models and languages

## Running the Server

### Start the Server

**Using UV (Recommended):**
```bash
uv run python fast-api/run_server.py
```

**Using standard Python:**
```bash
python fast-api/run_server.py
```

You should see:
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Access the API Documentation

Open your browser and go to:
- **Interactive API Docs**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc

## Download Models (Optional but Recommended)

Models auto-download on first use, but you can pre-download them for faster initial responses:

```bash
uv run python fast-api/scripts/download_models.py
```

This downloads ~350-500MB of core models (detection, OCR, inpainting). **First-time API calls will be slow without this step** as models download on demand.

Check model status anytime:
```bash
curl http://localhost:8000/api/v1/models
```

## Testing the API

### Method 1: Using the Test Client

```bash
uv run python fast-api/scripts/test_client.py path/to/manga_image.jpg
```

This will run all API endpoints and show the results.

### Method 2: Using curl

**Health Check:**
```bash
curl http://localhost:8000/health
```

**Full Translation Pipeline:**
```bash
curl -X POST "http://localhost:8000/api/v1/translate" \
  -F "file=@manga_page.jpg" \
  -F "source_lang=Japanese" \
  -F "target_lang=English"
```

### Method 3: Using Python

```python
import requests

# Translate a manga page
url = "http://localhost:8000/api/v1/translate"
files = {"file": open("manga_page.jpg", "rb")}
data = {
    "source_lang": "Japanese",
    "target_lang": "English"
}

response = requests.post(url, files=files, data=data)
result = response.json()

for block in result['blocks']:
    print(f"{block['text']} → {block['translation']}")
```

## API Endpoints Overview

| Endpoint | Purpose | Example |
|----------|---------|---------|
| `POST /api/v1/detection` | Detect text blocks | Find text regions in image |
| `POST /api/v1/ocr` | Extract text (OCR) | Read Japanese text |
| `POST /api/v1/translation` | Translate text | Japanese → English |
| `POST /api/v1/inpainting` | Remove text | Clean text from image |
| `POST /api/v1/translate` | Full pipeline | Do everything at once |

## Common Use Cases

### 1. Quick Translation (One Step)

Use the full pipeline endpoint for the easiest approach:

```bash
curl -X POST "http://localhost:8000/api/v1/translate" \
  -F "file=@manga.jpg" \
  -F "source_lang=Japanese" \
  -F "target_lang=English"
```

### 2. Translation with Context

Add extra context for better translations:

```bash
curl -X POST "http://localhost:8000/api/v1/translate" \
  -F "file=@manga.jpg" \
  -F "source_lang=Japanese" \
  -F "target_lang=English" \
  -F "extra_context=This is a fantasy manga about dragons"
```

### 3. Remove Text from Image

Get a clean image with text removed:

```bash
curl -X POST "http://localhost:8000/api/v1/translate" \
  -F "file=@manga.jpg" \
  -F "source_lang=Japanese" \
  -F "target_lang=English" \
  -F "include_inpainted=true"
```

### 4. Batch Processing Multiple Images

```python
import requests
import os

def translate_page(image_path):
    url = "http://localhost:8000/api/v1/translate"
    with open(image_path, "rb") as f:
        files = {"file": f}
        data = {
            "source_lang": "Japanese",
            "target_lang": "English"
        }
        response = requests.post(url, files=files, data=data)
        return response.json()

# Process entire manga chapter
for filename in os.listdir("manga_chapter"):
    if filename.endswith(".jpg"):
        result = translate_page(f"manga_chapter/{filename}")
        print(f"Translated {filename}: {result['count']} blocks")
```

## Supported Languages

**Common source languages:**
- Japanese (most common for manga)
- Korean (manhwa)
- Chinese (manhua)

**Target languages:**
- English, Spanish, French, German, Italian
- Portuguese, Russian, Arabic
- And 15+ more languages

## Performance Tips

1. **First run is slower** - Models need to download (happens once)
2. **Enable GPU** - Set `ENABLE_GPU=True` in `.env` for 5-10x speedup
3. **Keep server running** - Models stay loaded in memory between requests
4. **Reduce image size** - Smaller images process faster (resize to ~1500px max dimension)

## Troubleshooting

**Server won't start:**
```bash
# Check if port is in use
netstat -ano | findstr :8000

# Try a different port
# Edit .env and change PORT=8001
```

**Out of memory:**
- Process smaller images
- Disable GPU if VRAM is limited
- Process images one at a time

**Slow processing:**
- Enable GPU acceleration
- Models are downloading (check logs)
- Network issues with cloud OCR/translation services

## Next Steps

- Read the [full API documentation](API_README.md) for detailed endpoint information
- Explore the interactive docs at http://localhost:8000/docs
- Try different models and translators for better results
- Integrate the API into your own applications

## Getting Help

- Check server logs for error details
- Visit http://localhost:8000/docs for interactive API testing
- Review the [API README](API_README.md) for comprehensive documentation
- Check the main [project repository](https://github.com/ogkalu2/comic-translate)

---

**Ready to go!** Your manga translation API server is now running and ready to process images. 🚀
