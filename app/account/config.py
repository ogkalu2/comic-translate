# Localhost URLs for development environment
# Use 127.0.0.1 instead of localhost to avoid IPv6 resolution/fallback delays on some Windows setups.
# dev_api_base_url = "http://127.0.0.1:8000"
# dev_frontend_base_url = "http://127.0.0.1:3000"

dev_api_base_url = "http://localhost:8000"
dev_frontend_base_url = "http://localhost:3000"

# Production URLs
prod_api_base_url = "https://api.comic-translate.com"
prod_frontend_base_url = "https://www.comic-translate.com"

API_BASE_URL = prod_api_base_url
FRONTEND_BASE_URL = prod_frontend_base_url
WEB_API_OCR_URL = f"{API_BASE_URL}/api/v1/ocr"
WEB_API_TRANSLATE_URL = f"{API_BASE_URL}/api/v1/translate"