import base64
import cv2
import numpy as np
import requests
from typing import List, Dict, Any

from .base import OCREngine
from ..utils.textblock import TextBlock, adjust_text_line_coordinates

class QwenOCREngine(OCREngine):
    """OCR engine using Qwen 2.5 VL model (free version) via OpenRouter API."""
    
    def __init__(self):
        """Initialize Qwen OCR engine."""
        self.api_key = None
        self.expansion_percentage = 0
        self.model = "qwen/qwen2.5-vl-72b-instruct:free"
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.prompt = "Riconosci il testo nell'immagine. Scrivi esattamente il testo come appare, NON tradurre."
        
    def initialize(self, api_key: str, prompt: str = None,
                   expansion_percentage: int = 0, **kwargs) -> None:
        """
        Initialize the Qwen OCR with API key and parameters.
        
        Args:
            api_key: OpenRouter API key
            prompt: Custom prompt to use for OCR (optional)
            expansion_percentage: Percentage to expand text bounding boxes
            **kwargs: Additional parameters (ignored)
        """
        self.api_key = api_key
        if prompt:
            self.prompt = prompt
        self.expansion_percentage = expansion_percentage
        
    @staticmethod
    def verify_api_key(api_key: str) -> dict:
        """
        Verify if the API key is valid by making a simple test request.
        Also returns usage information if available.
        
        Args:
            api_key: OpenRouter API key to verify
            
        Returns:
            Dictionary with validation result and usage information if available
        """
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            # Verify the API key
            auth_response = requests.get("https://openrouter.ai/api/v1/auth/key", headers=headers)
            print(f"Auth response status: {auth_response.status_code}")
            
            # If key is valid, try to get usage information
            if auth_response.status_code == 200:
                # Verifichiamo che la risposta contenga dati
                try:
                    if auth_response.text and auth_response.text.strip():
                        auth_data = auth_response.json()
                        print(f"Auth data: {auth_data}")
                except Exception as json_error:
                    print(f"Auth data is not valid JSON: {auth_response.text}, error: {str(json_error)}")
                    auth_data = {}
                
                # Get usage information from models endpoint (più affidabile di activity)
                models_response = requests.get("https://openrouter.ai/api/v1/models", headers=headers)
                print(f"Models response status: {models_response.status_code}")
                
                # Se entrambe le chiamate ritornano 200, l'API key è valida
                if models_response.status_code == 200:
                    return {
                        "valid": True,
                        "usage": None  # Non prendiamo l'usage perché può causare errori
                    }
                else:
                    # API key sembra valida ma non possiamo ottenere altri dati
                    return {
                        "valid": True,
                        "usage": None
                    }
            
            # Key is not valid
            return {
                "valid": False,
                "usage": None
            }
        except Exception as e:
            print(f"Error verifying API key: {str(e)}")
            return {
                "valid": False,
                "usage": None,
                "error": str(e)
            }

    def process_image(self, img: np.ndarray, blk_list: List[TextBlock]) -> List[TextBlock]:
        """
        Process an image with Qwen-based OCR by processing individual text regions.
        
        Args:
            img: Input image as numpy array
            blk_list: List of TextBlock objects to update with OCR text
            
        Returns:
            List of updated TextBlock objects with recognized text
        """
        for blk in blk_list:
            try:
                # Get box coordinates
                if blk.bubble_xyxy is not None:
                    x1, y1, x2, y2 = blk.bubble_xyxy
                else:
                    x1, y1, x2, y2 = adjust_text_line_coordinates(
                        blk.xyxy,
                        self.expansion_percentage,
                        self.expansion_percentage,
                        img
                    )
                
                # Check if coordinates are valid
                if x1 < x2 and y1 < y2 and x1 >= 0 and y1 >= 0 and x2 <= img.shape[1] and y2 <= img.shape[0]:
                    # Crop image and encode
                    cropped_img = img[y1:y2, x1:x2]
                    cv2_encoded = cv2.imencode('.png', cropped_img)[1]
                    base64_img = base64.b64encode(cv2_encoded).decode('utf-8')
                    
                    # Get OCR result from Qwen
                    data = {
                        "model": self.model,
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": self.prompt},
                                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_img}"}}
                                ]
                            }
                        ]
                    }
                    headers = {
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    }
                    response = requests.post(self.api_url, headers=headers, json=data)
                    response.raise_for_status()  # Raise exception if request failed
                    
                    result = response.json()
                    if 'choices' in result:
                        text = result["choices"][0]["message"]["content"]
                    else:
                        print(f"Unexpected response format: {result}")
                        blk.text = ""
                        continue
                    
                    # Replace newlines with spaces
                    blk.text = text.replace('\n', ' ') if '\n' in text else text
            except Exception as e:
                print(f"Qwen OCR error on block: {str(e)}")
                blk.text = ""
                
        return blk_list

class QwenFullOCREngine(OCREngine):
    """OCR engine using Qwen 2.5 VL model (paid version) via OpenRouter API."""
    
    def __init__(self):
        """Initialize Qwen OCR engine."""
        self.api_key = None
        self.expansion_percentage = 0
        self.model = "qwen/qwen2.5-vl-72b-instruct"
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.prompt = "Riconosci il testo nell'immagine. Scrivi esattamente il testo come appare, NON tradurre."
        
    def initialize(self, api_key: str, prompt: str = None,
                   expansion_percentage: int = 0, **kwargs) -> None:
        """
        Initialize the Qwen OCR with API key and parameters.
        
        Args:
            api_key: OpenRouter API key
            prompt: Custom prompt to use for OCR (optional)
            expansion_percentage: Percentage to expand text bounding boxes
            **kwargs: Additional parameters (ignored)
        """
        self.api_key = api_key
        if prompt:
            self.prompt = prompt
        self.expansion_percentage = expansion_percentage
        
    def process_image(self, img: np.ndarray, blk_list: List[TextBlock]) -> List[TextBlock]:
        """
        Process an image with Qwen-based OCR by processing individual text regions.
        
        Args:
            img: Input image as numpy array
            blk_list: List of TextBlock objects to update with OCR text
            
        Returns:
            List of updated TextBlock objects with recognized text
        """
        for blk in blk_list:
            try:
                # Get box coordinates
                if blk.bubble_xyxy is not None:
                    x1, y1, x2, y2 = blk.bubble_xyxy
                else:
                    x1, y1, x2, y2 = adjust_text_line_coordinates(
                        blk.xyxy,
                        self.expansion_percentage,
                        self.expansion_percentage,
                        img
                    )
                
                # Check if coordinates are valid
                if x1 < x2 and y1 < y2 and x1 >= 0 and y1 >= 0 and x2 <= img.shape[1] and y2 <= img.shape[0]:
                    # Crop image and encode
                    cropped_img = img[y1:y2, x1:x2]
                    cv2_encoded = cv2.imencode('.png', cropped_img)[1]
                    base64_img = base64.b64encode(cv2_encoded).decode('utf-8')
                    
                    # Get OCR result from Qwen
                    data = {
                        "model": self.model,
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": self.prompt},
                                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_img}"}}
                                ]
                            }
                        ]
                    }
                    headers = {
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    }
                    response = requests.post(self.api_url, headers=headers, json=data)
                    response.raise_for_status()  # Raise exception if request failed
                    
                    result = response.json()
                    if 'choices' in result:
                        text = result["choices"][0]["message"]["content"]
                    else:
                        print(f"Unexpected response format: {result}")
                        blk.text = ""
                        continue
                    
                    # Replace newlines with spaces
                    blk.text = text.replace('\n', ' ') if '\n' in text else text
            except Exception as e:
                print(f"Qwen OCR error on block: {str(e)}")
                blk.text = ""
                
        return blk_list
    
    def _get_qwen_ocr(self, base64_image: str) -> str:
        """
        Get OCR result from Qwen VL model.
        
        Args:
            base64_image: Base64 encoded image
            
        Returns:
            OCR result text
        """
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": self.prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                        ]
                    }
                ]
            }
            
            response = requests.post(self.api_url, headers=headers, json=data)
            response.raise_for_status()  # Raise exception if request failed
            
            result = response.json()
            if 'choices' in result:
                text = result["choices"][0]["message"]["content"]
            else:
                print(f"Unexpected response format: {result}")
                return ""
            
            # Replace newlines with spaces
            return text.replace('\n', ' ') if '\n' in text else text
        except Exception as e:
            print(f"Qwen API error: {str(e)}")
            return ""
    
    @staticmethod
    def verify_api_key(api_key: str) -> dict:
        """
        Verify if the API key is valid by making a simple test request.
        Also returns usage information if available.
        
        Args:
            api_key: OpenRouter API key to verify
            
        Returns:
            Dictionary with validation result and usage information if available
        """
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            # Verify the API key
            auth_response = requests.get("https://openrouter.ai/api/v1/auth/key", headers=headers)
            print(f"Auth response status (Full): {auth_response.status_code}")
            
            # If key is valid, try to get usage information
            if auth_response.status_code == 200:
                # Verifichiamo che la risposta contenga dati
                try:
                    if auth_response.text and auth_response.text.strip():
                        auth_data = auth_response.json()
                        print(f"Auth data (Full): {auth_data}")
                except Exception as json_error:
                    print(f"Auth data is not valid JSON (Full): {auth_response.text}, error: {str(json_error)}")
                    auth_data = {}
                
                # Get usage information from models endpoint (più affidabile di activity)
                models_response = requests.get("https://openrouter.ai/api/v1/models", headers=headers)
                print(f"Models response status (Full): {models_response.status_code}")
                
                # Se entrambe le chiamate ritornano 200, l'API key è valida
                if models_response.status_code == 200:
                    return {
                        "valid": True,
                        "usage": None  # Non prendiamo l'usage perché può causare errori
                    }
                else:
                    # API key sembra valida ma non possiamo ottenere altri dati
                    return {
                        "valid": True,
                        "usage": None
                    }
            
            # Key is not valid
            return {
                "valid": False,
                "usage": None
            }
        except Exception as e:
            print(f"Error verifying API key: {str(e)}")
            return {
                "valid": False,
                "usage": None,
                "error": str(e)
            }

class QwenVLPlusOCR(OCREngine):
    """
    Qwen Max OCR engine.
    """

    def __init__(self, settings):
        super().__init__()  # Do not pass settings to the superclass
        self.model_name = 'Qwen Max'
        self.settings = settings
        self.api_key = self.get_credentials()  # Recupera la chiave API
        self.model = 'qwen/qwen-vl-2.5'
        self.prompt = "Riconosci il testo nell'immagine. Scrivi esattamente il testo come appare, NON tradurre."

    def initialize(self, api_key: str, **kwargs):
        """
        Inizializza il motore OCR con la chiave API.
        """
        self.api_key = api_key

    def process_image(self, img: np.ndarray, blk_list: List[TextBlock]) -> List[TextBlock]:
        """
        Processa l'immagine e restituisce il testo riconosciuto.
        """
        for blk in blk_list:
            try:
                # Costruzione della richiesta
                headers = self._get_headers()
                _, buffer = cv2.imencode('.png', img)
                base64_image = base64.b64encode(buffer).decode('utf-8')
                data = {
                    "model": self.model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": self.prompt},
                                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                            ]
                        }
                    ]
                }
                response = requests.post('https://openrouter.ai/api/v1/chat/completions', headers=headers, json=data)

                # Controllo della risposta
                if response.status_code == 200:
                    result = response.json()
                    if 'choices' in result:
                        text = result["choices"][0]["message"]["content"]
                    else:
                        print(f"Unexpected response format: {result}")
                        blk.text = ""
                        continue
                    
                    blk.text = text.replace('\n', ' ') if '\n' in text else text
                else:
                    print(f'Error: {response.status_code} - {response.text}')  # Log dell'errore
                    blk.text = None
            except Exception as e:
                print(f'Exception occurred: {str(e)}')  # Log dell'eccezione
                blk.text = None
        return blk_list

    def recognize(self, image):
        """
        Invia una richiesta di riconoscimento all'API Qwen Max e restituisce il testo riconosciuto.
        """
        try:
            # Costruzione della richiesta
            headers = self._get_headers()
            payload = {'image': image}
            response = requests.post('https://api.qwen.com/v1/ocr', headers=headers, json=payload)

            # Controllo della risposta
            if response.status_code == 200:
                result = response.json()
                return result['text']  # Restituisce il testo riconosciuto
            else:
                print(f'Error: {response.status_code} - {response.text}')  # Log dell'errore
                return None
        except Exception as e:
            print(f'Exception occurred: {str(e)}')  # Log dell'eccezione
            return None

    def _get_headers(self):
        """
        Crea gli headers per le richieste API.
        """
        return {'Authorization': f'Bearer {self.api_key}', 'Content-Type': 'application/json'}

    def get_credentials(self):
        """
        Retrieve the API credentials for Qwen Max.
        """
        # Assuming credentials are stored in a settings object or similar structure
        credentials = self.settings.get_credentials(self.settings.ui.tr("Qwen-Max"))
        print(f"Retrieved credentials for Qwen-Max: {credentials}")
        return credentials


class QwenMaxOCR(OCREngine):
    """
    Qwen-Max OCR engine.
    """

    def __init__(self, settings):
        super().__init__()  # Do not pass settings to the superclass
        self.model_name = 'Qwen-Max'
        self.settings = settings
        self.api_key = self.get_credentials()  # Recupera la chiave API
        self.model = 'qwen/qwen-vl-2.5'
        self.prompt = "Riconosci il testo nell'immagine. Scrivi esattamente il testo come appare, NON tradurre."

    def initialize(self, api_key: str, **kwargs):
        """
        Inizializza il motore OCR con la chiave API.
        """
        self.api_key = api_key

    def process_image(self, img: np.ndarray, blk_list: List[TextBlock]) -> List[TextBlock]:
        """
        Processa l'immagine e restituisce il testo riconosciuto.
        """
        for blk in blk_list:
            try:
                print(f"Using model: {self.model}")
                headers = self._get_headers()
                _, buffer = cv2.imencode('.png', img)
                base64_image = base64.b64encode(buffer).decode('utf-8')
                data = {
                    "model": self.model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": self.prompt},
                                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                            ]
                        }
                    ]
                }
                response = requests.post('https://openrouter.ai/api/v1/chat/completions', headers=headers, json=data)

                if response.status_code == 200:
                    result = response.json()
                    if 'choices' in result:
                        text = result["choices"][0]["message"]["content"]
                    else:
                        print(f"Unexpected response format: {result}")
                        blk.text = ""
                        continue
                    blk.text = text.replace('\n', ' ') if '\n' in text else text
                else:
                    print(f'Error: {response.status_code} - {response.text}')  # Log dell'errore
                    blk.text = None
            except Exception as e:
                print(f'Exception occurred: {str(e)}')  # Log dell'eccezione
                blk.text = None
        return blk_list

    def recognize(self, image):
        """
        Invia una richiesta di riconoscimento all'API Qwen Max e restituisce il testo riconosciuto.
        """

    def _get_headers(self):
        """
        Crea gli headers per le richieste API.
        """
        return {'Authorization': f'Bearer {self.api_key}', 'Content-Type': 'application/json'}

    def get_credentials(self):
        """
        Retrieve the API credentials for Qwen Max.
        """
        # Assuming credentials are stored in a settings object or similar structure
        credentials = self.settings.get_credentials(self.settings.ui.tr("Qwen-Max"))
        print(f"Retrieved credentials for Qwen-Max: {credentials}")
        return credentials
