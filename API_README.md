# Manga Translation API Documentation

A powerful REST API backend for manga image translation with support for text detection, OCR, translation, and inpainting.

## Features

- **Text Detection**: Automatically detect text regions in manga images
- **OCR (Optical Character Recognition)**: Extract text from detected regions
- **Translation**: Translate extracted text to target language
- **Inpainting**: Remove original text from images
- **Full Pipeline**: Complete end-to-end translation workflow

## Installation

### Prerequisites

- Python 3.8 or higher
- pip package manager
- (Optional) CUDA-capable GPU for acceleration

### Setup

1. **Clone the repository** (or navigate to your project directory):
```bash
cd comic-translate
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Download required models** (if needed):
The application will automatically download required models on first use.

## Running the Server

### Quick Start

```bash
python run_server.py
```

The server will start on `http://localhost:8000`

### Configuration

Create a `.env` file in the project root to customize settings:

```env
# Server settings
HOST=0.0.0.0
PORT=8000
RELOAD=True
LOG_LEVEL=info

# Model settings
DEFAULT_DETECTOR=RT-DETR-V2
DEFAULT_OCR=Default
DEFAULT_TRANSLATOR=Google Translate
DEFAULT_INPAINTER=LaMa

# GPU settings
ENABLE_GPU=False

# Language settings
DEFAULT_SOURCE_LANG=Japanese
DEFAULT_TARGET_LANG=English
```

## API Endpoints

### Base URL
```
http://localhost:8000
```

### Interactive API Documentation
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Chaining API Calls

The API endpoints can be chained together by passing the output of one endpoint to the next:

1. **Detection → OCR**: Pass the full detection response to OCR
2. **OCR → Translation**: Pass the full OCR response to translation
3. **Any → Inpainting**: Pass blocks to inpainting

**Important**: The `blocks` parameter accepts either:
- The **full response object** from a previous endpoint (e.g., `{"blocks": [...], "count": 5}`)
- Just the **blocks array** (e.g., `[{...}, {...}]`)

Both formats are automatically handled by the API.

---

## 1. Text Detection

**Endpoint**: `POST /api/v1/detection`

Detect text blocks in a manga image.

### Request

```bash
curl -X POST "http://localhost:8000/api/v1/detection" \
  -F "file=@manga_page.jpg" \
  -F "detector=RT-DETR-V2" \
  -F "gpu=false"
```

### Parameters

- `file` (required): Manga image file (JPEG, PNG)
- `detector` (optional): Detection model to use
  - Default: `RT-DETR-V2`
  - Options: `RT-DETR-V2`
- `gpu` (optional): Enable GPU acceleration (default: `false`)

### Response

```json
{
  "blocks": [
    {
      "bbox": [100, 50, 300, 150],
      "text": "",
      "translation": "",
      "text_class": "text_free",
      "angle": 0,
      "source_lang": "",
      "target_lang": "",
      "bubble_bbox": null,
      "inpaint_bboxes": null
    }
  ],
  "count": 10,
  "image_shape": [1200, 800, 3]
}
```

### Python Example

```python
import requests

url = "http://localhost:8000/api/v1/detection"
files = {"file": open("manga_page.jpg", "rb")}
data = {"detector": "RT-DETR-V2", "gpu": False}

response = requests.post(url, files=files, data=data)
result = response.json()
print(f"Detected {result['count']} text blocks")
```

---

## 2. OCR (Optical Character Recognition)

**Endpoint**: `POST /api/v1/ocr`

Perform OCR on manga image to extract text.

### Request

```bash
curl -X POST "http://localhost:8000/api/v1/ocr" \
  -F "file=@manga_page.jpg" \
  -F "source_lang=Japanese" \
  -F "ocr_model=Default" \
  -F "gpu=false"
```

### Parameters

- `file` (required): Manga image file
- `source_lang` (required): Source language
  - Examples: `Japanese`, `Korean`, `Chinese`, `English`
- `ocr_model` (optional): OCR model to use
  - Default: `Default`
  - Options: `Default`, `Microsoft OCR`, `Google Cloud Vision`, `GPT-4.1-mini`, `Gemini-2.0-Flash`
- `gpu` (optional): Enable GPU acceleration
- `blocks` (optional): JSON string of pre-detected text blocks

### Response

```json
{
  "blocks": [
    {
      "bbox": [100, 50, 300, 150],
      "text": "こんにちは",
      "translation": "",
      "text_class": "text_free",
      "angle": 0,
      "source_lang": "ja",
      "target_lang": ""
    }
  ],
  "count": 10,
  "source_lang": "Japanese"
}
```

### Python Example

```python
import requests
import json

# Example 1: OCR without pre-detected blocks
url = "http://localhost:8000/api/v1/ocr"
files = {"file": open("manga_page.jpg", "rb")}
data = {
    "source_lang": "Japanese",
    "ocr_model": "Default",
    "gpu": False
}

response = requests.post(url, files=files, data=data)
result = response.json()
for block in result['blocks']:
    print(f"Text: {block['text']}")

# Example 2: OCR with pre-detected blocks (chain from detection)
# First, get detection results
detection_response = requests.post(
    "http://localhost:8000/api/v1/detection",
    files={"file": open("manga_page.jpg", "rb")}
)
detection_result = detection_response.json()

# Then, use those blocks for OCR (pass full response as JSON string)
files = {"file": open("manga_page.jpg", "rb")}
data = {
    "source_lang": "Japanese",
    "ocr_model": "Default",
    "blocks": json.dumps(detection_result)  # Pass full detection response
}

response = requests.post(url, files=files, data=data)
result = response.json()
```

---

## 3. Translation

**Endpoint**: `POST /api/v1/translation`

Translate text extracted from manga image.

### Request

```bash
curl -X POST "http://localhost:8000/api/v1/translation" \
  -F "file=@manga_page.jpg" \
  -F "source_lang=Japanese" \
  -F "target_lang=English" \
  -F "translator=Google Translate" \
  -F "gpu=false"
```

### Parameters

- `file` (required): Manga image file
- `source_lang` (required): Source language
- `target_lang` (required): Target language
- `translator` (optional): Translation engine
  - Default: `Google Translate`
  - Options: `Google Translate`, `Microsoft Translator`, `DeepL`, `GPT-4.1`, `Claude-4.5-Sonnet`, `Gemini-2.5-Flash`
- `gpu` (optional): Enable GPU acceleration
- `blocks` (optional): JSON string of text blocks with OCR results
- `extra_context` (optional): Additional context for translation

### Response

```json
{
  "blocks": [
    {
      "bbox": [100, 50, 300, 150],
      "text": "こんにちは",
      "translation": "Hello",
      "text_class": "text_free",
      "angle": 0,
      "source_lang": "ja",
      "target_lang": "en"
    }
  ],
  "count": 10,
  "source_lang": "Japanese",
  "target_lang": "English"
}
```

### Python Example

```python
import requests

url = "http://localhost:8000/api/v1/translation"
files = {"file": open("manga_page.jpg", "rb")}
data = {
    "source_lang": "Japanese",
    "target_lang": "English",
    "translator": "Google Translate",
    "extra_context": "This is a romantic comedy manga"
}

response = requests.post(url, files=files, data=data)
result = response.json()
for block in result['blocks']:
    print(f"Original: {block['text']} -> Translation: {block['translation']}")
```

---

## 4. Inpainting

**Endpoint**: `POST /api/v1/inpainting`

Remove original text from manga image.

### Request

```bash
curl -X POST "http://localhost:8000/api/v1/inpainting" \
  -F "file=@manga_page.jpg" \
  -F "inpainter=LaMa" \
  -F "gpu=false"
```

### Parameters

- `file` (required): Manga image file
- `inpainter` (optional): Inpainting model
  - Default: `LaMa`
  - Options: `LaMa`, `MI-GAN`, `AOT`
- `gpu` (optional): Enable GPU acceleration
- `blocks` (optional): JSON string of text blocks to inpaint

### Response

```json
{
  "inpainted_image": "base64_encoded_image_data...",
  "blocks_count": 10,
  "image_shape": [1200, 800, 3]
}
```

### Python Example

```python
import requests
import base64
from PIL import Image
import io

url = "http://localhost:8000/api/v1/inpainting"
files = {"file": open("manga_page.jpg", "rb")}
data = {"inpainter": "LaMa", "gpu": False}

response = requests.post(url, files=files, data=data)
result = response.json()

# Decode and save inpainted image
image_data = base64.b64decode(result['inpainted_image'])
image = Image.open(io.BytesIO(image_data))
image.save("inpainted_manga.png")
```

---

## 5. Full Translation Pipeline

**Endpoint**: `POST /api/v1/translate`

Complete end-to-end translation: detection → OCR → translation → optional inpainting.

### Request

```bash
curl -X POST "http://localhost:8000/api/v1/translate" \
  -F "file=@manga_page.jpg" \
  -F "source_lang=Japanese" \
  -F "target_lang=English" \
  -F "detector=RT-DETR-V2" \
  -F "ocr_model=Default" \
  -F "translator=Google Translate" \
  -F "inpainter=LaMa" \
  -F "gpu=false" \
  -F "include_inpainted=true"
```

### Parameters

- `file` (required): Manga image file
- `source_lang` (required): Source language
- `target_lang` (required): Target language
- `detector` (optional): Detection model (default: `RT-DETR-V2`)
- `ocr_model` (optional): OCR model (default: `Default`)
- `translator` (optional): Translation engine (default: `Google Translate`)
- `inpainter` (optional): Inpainting model (default: `LaMa`)
- `gpu` (optional): Enable GPU acceleration (default: `false`)
- `extra_context` (optional): Additional translation context
- `include_inpainted` (optional): Include inpainted image in response (default: `false`)

### Response

```json
{
  "blocks": [
    {
      "bbox": [100, 50, 300, 150],
      "text": "こんにちは",
      "translation": "Hello",
      "text_class": "text_free",
      "angle": 0,
      "source_lang": "ja",
      "target_lang": "en"
    }
  ],
  "count": 10,
  "source_lang": "Japanese",
  "target_lang": "English",
  "pipeline_steps": ["detection", "ocr", "translation", "inpainting"],
  "inpainted_image": "base64_encoded_image_data..."
}
```

### Python Example

```python
import requests
import json

url = "http://localhost:8000/api/v1/translate"
files = {"file": open("manga_page.jpg", "rb")}
data = {
    "source_lang": "Japanese",
    "target_lang": "English",
    "detector": "RT-DETR-V2",
    "ocr_model": "Default",
    "translator": "Google Translate",
    "inpainter": "LaMa",
    "include_inpainted": True,
    "extra_context": "Fantasy adventure manga"
}

response = requests.post(url, files=files, data=data)
result = response.json()

print(f"Pipeline steps: {result['pipeline_steps']}")
print(f"Processed {result['count']} text blocks")

# Save translations
for i, block in enumerate(result['blocks']):
    print(f"Block {i+1}:")
    print(f"  Original: {block['text']}")
    print(f"  Translation: {block['translation']}")
```

---

## Health Check

**Endpoint**: `GET /health`

Check if the API server is running.

```bash
curl http://localhost:8000/health
```

**Response**:
```json
{
  "status": "healthy",
  "service": "manga-translation-api"
}
```

---

## Supported Languages

### Source & Target Languages

- Japanese
- Korean
- Chinese (Simplified & Traditional)
- English
- Russian
- French
- German
- Dutch
- Spanish
- Italian
- Turkish
- Polish
- Portuguese
- Brazilian Portuguese
- Thai
- Vietnamese
- Indonesian
- Hungarian
- Finnish
- Arabic

---

## Error Handling

All endpoints return standard HTTP status codes:

- `200 OK`: Successful request
- `400 Bad Request`: Invalid input (e.g., invalid image file)
- `422 Unprocessable Entity`: Validation error (missing required parameters)
- `500 Internal Server Error`: Server-side error

### Error Response Format

```json
{
  "detail": "Error message description",
  "error": "Detailed error information"
}
```

---

## Advanced Usage

### Chaining Operations

You can chain operations by passing the output of one endpoint to another:

```python
import requests
import json

# Step 1: Detection
detection_response = requests.post(
    "http://localhost:8000/api/v1/detection",
    files={"file": open("manga_page.jpg", "rb")},
    data={"detector": "RT-DETR-V2"}
)
blocks = detection_response.json()['blocks']

# Step 2: OCR with detected blocks
ocr_response = requests.post(
    "http://localhost:8000/api/v1/ocr",
    files={"file": open("manga_page.jpg", "rb")},
    data={
        "source_lang": "Japanese",
        "blocks": json.dumps(blocks)
    }
)
ocr_blocks = ocr_response.json()['blocks']

# Step 3: Translation with OCR results
translation_response = requests.post(
    "http://localhost:8000/api/v1/translation",
    files={"file": open("manga_page.jpg", "rb")},
    data={
        "source_lang": "Japanese",
        "target_lang": "English",
        "blocks": json.dumps(ocr_blocks)
    }
)
final_result = translation_response.json()
```

### Batch Processing

For processing multiple images:

```python
import requests
import os

def translate_manga_page(image_path):
    url = "http://localhost:8000/api/v1/translate"
    with open(image_path, "rb") as f:
        files = {"file": f}
        data = {
            "source_lang": "Japanese",
            "target_lang": "English",
            "translator": "Google Translate"
        }
        response = requests.post(url, files=files, data=data)
        return response.json()

# Process multiple pages
manga_folder = "manga_pages"
for filename in os.listdir(manga_folder):
    if filename.endswith((".jpg", ".png")):
        image_path = os.path.join(manga_folder, filename)
        result = translate_manga_page(image_path)
        print(f"Processed {filename}: {result['count']} blocks translated")
```

---

## Performance Tips

1. **GPU Acceleration**: Enable GPU for faster processing on compatible hardware
2. **Caching**: The server caches model instances between requests
3. **Batch Processing**: Process multiple images in parallel using async requests
4. **Model Selection**: Choose appropriate models based on accuracy vs speed tradeoffs

---

## Troubleshooting

### Common Issues

**Issue**: Server won't start
- Check if port 8000 is already in use
- Verify all dependencies are installed: `pip install -r requirements.txt`

**Issue**: Out of memory errors
- Reduce image size before uploading
- Disable GPU acceleration if VRAM is limited
- Process images sequentially instead of in parallel

**Issue**: Slow processing
- Enable GPU acceleration for better performance
- Use lighter models (e.g., Default OCR instead of GPT-4.1-mini)
- Ensure models are downloaded and cached

---

## License

This project inherits the license from the original comic-translate project.

---

## Contributing

Contributions are welcome! Please ensure:
1. Code follows existing patterns
2. Add tests for new features
3. Update documentation

---

## Support

For issues and questions:
- Check the [main project repository](https://github.com/ogkalu2/comic-translate)
- Review API documentation at `/docs` endpoint
- Check server logs for detailed error messages
