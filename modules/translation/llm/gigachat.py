from typing import Any
import numpy as np
import requests
import json

from .base import BaseLLMTranslation
from ...utils.translator_utils import MODEL_MAP
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import base64
import uuid
import time
from datetime import datetime, timedelta

class GigaChatTokenManager:
    def __init__(self):
        self.CLIENT_ID = "019c6602-4a7e-7036-8764-16109e39b1e2"
        self.CLIENT_SECRET = "3df7b6e6-59e8-4910-8114-198482fb7751"
        self.access_token = None
        self.token_expires_at = None
        self.auth_string = base64.b64encode(f"{self.CLIENT_ID}:{self.CLIENT_SECRET}".encode()).decode()
    
    def get_token(self):
        """ВСЕГДА свежий токен при 401"""
        if not self._is_token_valid():
            print("🔄 Обновляем токен...")
            self._refresh_token()
        return self.access_token
    
    def _is_token_valid(self):
        return (self.access_token and 
                self.token_expires_at and 
                datetime.now() < (self.token_expires_at - timedelta(minutes=2)))
    
    def _refresh_token(self):
        url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        payload = {'scope': 'GIGACHAT_API_PERS', 'grant_type': 'client_credentials'}
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
            'RqUID': str(uuid.uuid4()),
            'Authorization': f'Basic {self.auth_string}'
        }
        
        response = requests.post(url, data=payload, headers=headers, verify=False, timeout=10)
        response.raise_for_status()
        
        token_data = response.json()
        self.access_token = token_data["access_token"]
        self.token_expires_at = datetime.now() + timedelta(seconds=token_data.get("expires_in", 1800))
        
        print(f"✅ Токен обновлён: {self.access_token[:20]}... (до {self.token_expires_at})")


# Глобальный менеджер токенов
token_manager = GigaChatTokenManager()


class GPTTranslation(BaseLLMTranslation):
    """Translation engine using OpenAI GPT models through direct REST API calls."""
    
    def __init__(self, config=None):
        self.token_manager = token_manager  # Используем глобальный
        self.api_key = self.token_manager.get_token()  # Получаем свежий
        self.api_base = "https://gigachat.devices.sberbank.ru/api/v1"
        self.model = "GigaChat"  # Твоя любимая модель!
        self.api_base_url = self.api_base.rstrip('/')
        self.timeout = 60

        
        # ✅ ОБЯЗАТЕЛЬНЫЕ атрибуты comic-translate
        self.supports_images = False  # GigaChat пока без vision
        self.supports_system_prompt = True
        self.name = "GigaChat"
        

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self.session = requests.Session()
        self.session.verify = False

    
    def initialize(self, settings: Any, source_lang: str, target_lang: str, model_name: str, **kwargs) -> None:
        """
        Initialize GPT translation engine.
        
        Args:
            settings: Settings object with credentials
            source_lang: Source language name
            target_lang: Target language name
            model_name: GPT model name
        """
        super().initialize(settings, source_lang, target_lang, **kwargs)
        
        self.model_name = model_name
        credentials = settings.get_credentials(settings.ui.tr('Open AI GPT'))
        self.api_key = credentials.get('api_key', '')
        self.model = MODEL_MAP.get(self.model_name)
    
    def _perform_translation(self, user_prompt: str, system_prompt: str, image: np.ndarray) -> str:
        """
        Perform translation using direct REST API calls to OpenAI.
        
        Args:
            user_prompt: Text prompt from user
            system_prompt: System instructions
            image: Image as numpy array
            
        Returns:
            Translated text
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        if self.supports_images and self.img_as_llm_input:
            # Use the base class method to encode the image
            encoded_image, mime_type = self.encode_image(image)
            
            messages = [
                {
                    "role": "system", 
                    "content": [{"type": "text", "text": system_prompt}]
                },
                {
                    "role": "user", 
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{encoded_image}"}}
                    ]
                }
            ]
        else:
            messages = [
                {
                    "role": "system", 
                    "content": [{"type": "text", "text": system_prompt}]
                },
                {
                    "role": "user", 
                    "content": [{"type": "text", "text": user_prompt}]
                }
            ]

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_completion_tokens": self.max_tokens,
            "top_p": self.top_p,
            "response_format": {"type": "json_object"},
        }

        return self._make_api_request(payload, headers)
    

    def _make_api_request(self, payload, headers):
        """GigaChat с автообновлением токена"""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                # ✅ 1. Свежий токен
                self.api_key = self.token_manager.get_token()
                headers['Authorization'] = f"Bearer {self.api_key}"
                
                if "gigachat" in self.api_base.lower():
                    headers['Content-Type'] = 'application/json'
                    
                    # ✅ 2. Обработка сообщений (ТВОЙ код из логов)
                    messages = []
                    for msg in payload.get("messages", []):
                        content = msg.get("content", "")
                        
                        # Рекурсивная обработка list→dict→str
                        while True:
                            if isinstance(content, list) and len(content) > 0:
                                content = content[0]
                            elif isinstance(content, dict):
                                content = content.get("text", "")
                            else:
                                break
                        
                        content = str(content).strip()
                        messages.append({
                            "role": msg.get("role", "user"),
                            "content": content
                        })
                    
                    # ✅ 3. request_payload создаём ЗДЕСЬ
                    request_payload = {
                        "model": "GigaChat-MAX",  # Твоя модель
                        "messages": messages,
                        "temperature": 0.1,
                        "max_tokens": 2048,
                        "response_format": {"type": "json_object"},
                        "stream": False
                    }
                    
                    print(f"📤 GigaChat: {request_payload}")
                
                else:
                    request_payload = payload  # OpenAI формат
                
                # ✅ 4. Отправка
                response = requests.post(
                    "https://gigachat.devices.sberbank.ru/api/v1/chat/completions",
                    headers=headers,
                    json=request_payload,  # Теперь определён!
                    timeout=60, 
                    verify=False
                )
                
                print(f"📥 Status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    return data["choices"][0]["message"]["content"]
                
                elif response.status_code == 401:
                    print(f"🔄 401 → Обновляем токен (попытка {attempt+1}/{max_retries})")
                    self.token_manager.access_token = None
                    continue
                    
                response.raise_for_status()
                
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"🔄 Retry {attempt+1}/{max_retries}: {e}")
                    continue
                print(f"❌ Финальная ошибка: {e}")
                raise
        
        raise RuntimeError("GigaChat: все попытки исчерпаны")





