# Localhost URLs for development environment
dev_api_base_url = "http://localhost:8000"
dev_frontend_base_url = "http://localhost:3000"

# Production URLs
prod_api_base_url = "https://www.comic-translate.com"
prod_frontend_base_url = "https://www.comic-translate.com"

API_BASE_URL = prod_api_base_url
FRONTEND_BASE_URL = prod_frontend_base_url
WEB_API_OCR_URL = f"{API_BASE_URL}/api/v1/ocr"
WEB_API_TRANSLATE_URL = f"{API_BASE_URL}/api/v1/translate"