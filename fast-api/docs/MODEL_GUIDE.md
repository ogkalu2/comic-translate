# Model Management Guide

This guide explains how models are downloaded and used in the Manga Translation API.

## How Models Work

The API uses AI models for different tasks:
- **Detection**: Find text regions in images (RT-DETR-V2)
- **OCR**: Extract text from images (Manga OCR, PPOCRv5)
- **Translation**: Translate text (Google Translate, DeepL, LLMs, etc.)
- **Inpainting**: Remove text from images (LaMa, MI-GAN, AOT)

## Automatic Model Download

Models are **automatically downloaded** when:
1. The server starts (core models only)
2. You first use a specific model through the API
3. You explicitly request model download via the API

**First-time usage will be slower** as models need to download (50MB - 500MB per model).

## Core Models (Auto-downloaded at Startup)

These models download automatically when the server starts:

| Model | Size | Purpose |
|-------|------|---------|
| RT-DETR-V2 | ~100MB | Text detection |
| Manga OCR ONNX | ~200MB | Japanese/Korean OCR |
| LaMa ONNX | ~50MB | Text inpainting |

## Available Models by Category

### Detection Models

- **RT-DETR-V2** (ONNX) - Text and bubble detection for manga/comics

### OCR Models

**For Japanese/Korean:**
- **Manga OCR** (ONNX) - Fast, accurate for manga
- **Manga OCR** (PyTorch) - More accurate but slower
- **Pororo** (ONNX) - Korean-focused OCR

**For Other Languages:**
- **PPOCRv5 Detection** - Text detection for any language
- **PPOCRv5 Chinese** - Chinese text recognition
- **PPOCRv5 English** - English text recognition
- **PPOCRv5 Korean** - Korean text recognition
- **PPOCRv5 Latin** - French, Spanish, German, Italian, Portuguese
- **PPOCRv5 Russian** - Russian and East Slavic languages

### Inpainting Models

- **LaMa** (ONNX) - Fast, good quality (recommended)
- **LaMa** (PyTorch) - Slower, slightly better quality
- **MI-GAN** (ONNX) - Manga-specific inpainting
- **MI-GAN** (PyTorch) - PyTorch version
- **AOT** (ONNX) - Alternative inpainting method
- **AOT** (PyTorch) - PyTorch version

## API Endpoints for Model Management

### 1. Check Model Status

Get information about which models are downloaded:

```bash
curl http://localhost:8000/api/v1/models
```

**Response:**
```json
{
  "models": {
    "detection": {
      "RT-DETR-V2": {
        "downloaded": true,
        "description": "Text and bubble detector (ONNX)"
      }
    },
    "ocr": {
      "Manga OCR (ONNX)": {
        "downloaded": true,
        "description": "Japanese/Korean manga OCR (ONNX)",
        "languages": ["Japanese", "Korean"]
      },
      ...
    },
    "inpainting": {
      "LaMa (ONNX)": {
        "downloaded": true,
        "description": "Large mask inpainting (ONNX, fast)"
      },
      ...
    }
  },
  "summary": {
    "total": 20,
    "downloaded": 3,
    "pending": 17
  }
}
```

### 2. Download Models

Explicitly download models before first use:

**Download all core models:**
```bash
curl -X POST http://localhost:8000/api/v1/models/download
```

**Download specific categories:**
```bash
curl -X POST http://localhost:8000/api/v1/models/download \
  -H "Content-Type: application/json" \
  -d '["detection", "ocr", "inpainting"]'
```

**Response:**
```json
{
  "status": "success",
  "downloaded": [
    "RT-DETR-V2 Detection",
    "Manga OCR (ONNX)",
    "PPOCRv5 Detection",
    "PPOCRv5 English",
    "LaMa (ONNX)"
  ],
  "message": "Successfully downloaded 5 model(s)"
}
```

## Using Different Models

### Detection

Currently only RT-DETR-V2 is supported:

```bash
curl -X POST "http://localhost:8000/api/v1/detection" \
  -F "file=@manga.jpg" \
  -F "detector=RT-DETR-V2"
```

### OCR

The `ocr_model` parameter determines which model to use:

**Default (auto-selects based on language):**
```bash
curl -X POST "http://localhost:8000/api/v1/ocr" \
  -F "file=@manga.jpg" \
  -F "source_lang=Japanese" \
  -F "ocr_model=Default"
```

**Cloud-based OCR (no local model needed):**
```bash
# Google Cloud Vision
curl -X POST "http://localhost:8000/api/v1/ocr" \
  -F "file=@manga.jpg" \
  -F "source_lang=Japanese" \
  -F "ocr_model=Google Cloud Vision"

# Microsoft OCR
curl -X POST "http://localhost:8000/api/v1/ocr" \
  -F "file=@manga.jpg" \
  -F "source_lang=Japanese" \
  -F "ocr_model=Microsoft OCR"
```

### Inpainting

Choose between different inpainting models:

```bash
# LaMa (recommended - fast and good quality)
curl -X POST "http://localhost:8000/api/v1/inpainting" \
  -F "file=@manga.jpg" \
  -F "inpainter=LaMa"

# MI-GAN (manga-specific)
curl -X POST "http://localhost:8000/api/v1/inpainting" \
  -F "file=@manga.jpg" \
  -F "inpainter=MI-GAN"

# AOT (alternative method)
curl -X POST "http://localhost:8000/api/v1/inpainting" \
  -F "file=@manga.jpg" \
  -F "inpainter=AOT"
```

## Model Download Locations

Models are stored in:
```
comic-translate/models/
├── detection/
│   └── detector.onnx
├── ocr/
│   ├── manga-ocr-base-onnx/
│   ├── ppocr-v5-onnx/
│   └── pororo-onnx/
└── inpainting/
    ├── lama-manga-dynamic.onnx
    ├── migan-pipeline-v2.onnx
    └── aot.onnx
```

## Python Client Examples

### Check Model Status

```python
import requests

response = requests.get("http://localhost:8000/api/v1/models")
models = response.json()

print(f"Total models: {models['summary']['total']}")
print(f"Downloaded: {models['summary']['downloaded']}")
print(f"Pending: {models['summary']['pending']}")

# Check specific model
if models['models']['ocr']['Manga OCR (ONNX)']['downloaded']:
    print("Manga OCR is ready!")
else:
    print("Manga OCR needs to be downloaded")
```

### Download Models

```python
import requests

# Download all core models
response = requests.post("http://localhost:8000/api/v1/models/download")
result = response.json()

print(f"Status: {result['status']}")
print(f"Downloaded: {', '.join(result['downloaded'])}")
```

### Use Specific Model

```python
import requests

# Use MI-GAN for inpainting instead of default LaMa
files = {"file": open("manga_page.jpg", "rb")}
data = {"inpainter": "MI-GAN"}

response = requests.post(
    "http://localhost:8000/api/v1/inpainting",
    files=files,
    data=data
)

result = response.json()
```

## Model Selection Recommendations

### For Japanese Manga:
- **Detection**: RT-DETR-V2 (only option)
- **OCR**: Manga OCR (Default) - best accuracy
- **Inpainting**: LaMa - fastest, good quality

### For Korean Manhwa:
- **Detection**: RT-DETR-V2
- **OCR**: Manga OCR or Pororo (Default)
- **Inpainting**: LaMa

### For Chinese Manhua:
- **Detection**: RT-DETR-V2
- **OCR**: PPOCRv5 Chinese (Default)
- **Inpainting**: LaMa

### For English Comics:
- **Detection**: RT-DETR-V2
- **OCR**: PPOCRv5 English (Default)
- **Inpainting**: LaMa

### For European Comics (French, Spanish, etc.):
- **Detection**: RT-DETR-V2
- **OCR**: PPOCRv5 Latin (Default)
- **Inpainting**: LaMa

## Troubleshooting

### Models Not Downloading

**Issue**: Models fail to download or timeout

**Solutions**:
1. Check internet connection
2. Models download from HuggingFace/ModelScope - ensure these sites are accessible
3. Try downloading manually and placing in `models/` directory
4. Check disk space (models can be 50MB - 500MB each)

### Slow First Request

**Issue**: First translation takes a very long time

**Cause**: Models are downloading on first use

**Solutions**:
1. Pre-download models: `curl -X POST http://localhost:8000/api/v1/models/download`
2. Monitor server logs to see download progress
3. Be patient - subsequent requests will be much faster

### Out of Memory

**Issue**: Server crashes with memory errors

**Cause**: Too many models loaded at once or model too large for available RAM

**Solutions**:
1. Use ONNX models (smaller and faster) instead of PyTorch
2. Restart server to clear model cache
3. Disable GPU if using GPU models with limited VRAM
4. Process smaller images

### Wrong Model Being Used

**Issue**: API uses different model than expected

**Cause**: "Default" option auto-selects model based on language

**Solution**: Explicitly specify the model you want to use instead of "Default"

## Advanced: Adding Custom Models

To add your own models:

1. Edit `modules/utils/download.py`
2. Register your model in `_register_defaults()`:

```python
ModelDownloader.register(ModelSpec(
    id=ModelID.YOUR_MODEL,
    url='https://your-url.com/',
    files=['model.onnx'],
    sha256=['checksum'],
    save_dir=os.path.join(models_base_dir, 'category')
))
```

3. Update the factory classes to use your model
4. Restart the server

## Model Performance Comparison

| Model Type | Speed | Accuracy | Memory | Use Case |
|------------|-------|----------|--------|----------|
| ONNX | ⚡⚡⚡ Fast | ⭐⭐⭐ Good | 💾 Low | Production |
| PyTorch | ⚡ Slow | ⭐⭐⭐⭐ Better | 💾💾 High | Quality-first |
| Cloud APIs | ⚡⚡ Medium | ⭐⭐⭐⭐ Better | 💾 None | No local resources |

**Recommendation**: Use ONNX models for the best balance of speed and accuracy.

## Next Steps

- Check your model status: `GET /api/v1/models`
- Pre-download models: `POST /api/v1/models/download`
- Test different models to find the best for your use case
- Monitor the server logs to see which models are being used

For more information, see the [API Documentation](API_README.md).
