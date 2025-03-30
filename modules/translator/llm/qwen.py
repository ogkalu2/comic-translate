import base64
import json
import os
import requests
from typing import Dict, Any, List, Optional

from ..base import TranslationEngine, LLMTranslation
from modules.utils.textblock import TextBlock

class QwenTranslation(TranslationEngine):
    """Translation engine using Qwen Max model via OpenRouter API."""
    
    def __init__(self, model_name="qwen/qwen-max"):
        """Initialize Qwen translation engine."""
        super().__init__()
        self.api_key = None
        self.model = model_name
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.prompt = "Generate a JSON response with 'translation' key containing the translated text from {src_lang} to {tgt_lang}. Maintain original meaning, style and tone. Text: {original_text}"
        self.include_image = True
        self.source_lang = None
        self.target_lang = None
        
    def initialize(self, settings, source_lang: str, target_lang: str, model_type: str = "", **kwargs):
        """
        Initialize Qwen translation with API key and parameters.
        
        Args:
            settings: Application settings object
            source_lang: Source language
            target_lang: Target language
            model_type: Model type (not used for Qwen)
            **kwargs: Additional parameters
        """
        super().initialize(settings, source_lang, target_lang)
        
        # Set language attributes
        self.source_lang = source_lang
        self.target_lang = target_lang
        
        # Get API key from settings
        self.api_key = settings.get_credentials("Qwen-Max")  # Update this line
        
        # Get custom prompt if available
        custom_prompt = settings.get_qwen_translate_prompt()
        if custom_prompt:
            self.prompt = custom_prompt
            
        # Check if we should include image
        self.include_image = settings.get_value("include_image_in_llm", True)
        
    def translate(self, blk_list: List[TextBlock], image_path: str | None = None, extra_context: str | None = None, **kwargs) -> List[TextBlock]:
        """Translate text using Qwen Max model."""
        if not self.api_key:
            raise ValueError("API key for Qwen Max is not set")
            
        # Use instance languages if not specified
        src_lang = self.source_lang or ""
        tgt_lang = self.target_lang or ""
        
        # Extract text from TextBlock objects
        texts = [block.text for block in blk_list]
        
        print("[DEBUG] Qwen Translator - Numero di blocchi da tradurre:", len(texts))
        
        # Traduciamo ogni blocco separatamente per mantenere la struttura
        for i, block in enumerate(blk_list):
            # Saltiamo blocchi vuoti
            if not block.text.strip():
                continue
                
            print(f"[DEBUG] Qwen Translator - Traduzione blocco {i+1}/{len(blk_list)}: {block.text}")
            
            # Format the prompt with language information and additional context if provided
            try:
                # Include extra context if available
                context_section = f"\nContesto aggiuntivo: {extra_context}" if extra_context else ""
                
                formatted_prompt = f"Traduci SOLO questo testo da {src_lang} a {tgt_lang}. Mantieni il significato originale e rispondi con JSON valido {{\"translation\": \"testo tradotto\"}}. Non includere altro testo o spiegazioni:{context_section}\n\n{block.text}"
                
                print(f"[DEBUG] Qwen Translator - Prompt per blocco {i+1}: {formatted_prompt[:100]}...")
            except Exception as e:
                print(f"[ERROR] Errore nella formattazione del prompt: {e}. Uso prompt di fallback")
                formatted_prompt = f"Traduci da {src_lang} a {tgt_lang}: {block.text}"
            
            # Build the message content
            message_content = [{
                "type": "text", 
                "text": formatted_prompt
            }]
            
            # Add image if available and inclusion is enabled only for the first block
            if i == 0 and image_path and self.include_image and os.path.exists(image_path):
                try:
                    with open(image_path, "rb") as img_file:
                        encoded_img = base64.b64encode(img_file.read()).decode('utf-8')
                    message_content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{encoded_img}"}
                    })
                    print("[DEBUG] Qwen Translator - Image included from:", image_path)
                except Exception as e:
                    print(f"Error including image in Qwen translation: {str(e)}")
            
            try:
                # Build request
                headers = {
                    "Authorization": f"Bearer {self.api_key['api_key'].strip()}",
                    "Content-Type": "application/json"
                }
                
                data = {
                    "model": self.model,
                    "messages": [
                        {
                            "role": "user",
                            "content": message_content
                        }
                    ]
                }
                
                # Send request
                response = requests.post(self.api_url, headers=headers, json=data)
                response.raise_for_status()
                
                # Process response
                result = response.json()
                
                if "choices" in result and len(result["choices"]) > 0:
                    translation = result["choices"][0]["message"]["content"]
                    
                    # Try to extract JSON response if present
                    try:
                        # Verifica se inizia con caratteri JSON
                        translation = translation.strip()
                        
                        # Gestione del formato JSON completo
                        if translation.startswith("{") and ("translation" in translation.lower() or "\"translation\"" in translation):
                            json_response = json.loads(translation)
                            if isinstance(json_response, dict) and "translation" in json_response:
                                # Prende la traduzione dal JSON e sostituisce le virgolette escapate con quelle normali
                                translated_text = json_response["translation"].replace('\\"', '"')
                            else:
                                translated_text = translation
                        # Gestione del formato JSON con codice di markdown
                        elif translation.startswith("```json") and "translation" in translation:
                            # Estrae il JSON dal blocco di codice markdown
                            json_text = translation.replace("```json", "").replace("```", "").strip()
                            json_response = json.loads(json_text)
                            if isinstance(json_response, dict) and "translation" in json_response:
                                translated_text = json_response["translation"].replace('\\"', '"')
                            else:
                                translated_text = translation
                        else:
                            translated_text = translation
                    except json.JSONDecodeError:
                        # Se non è JSON valido, usa il testo così com'è
                        translated_text = translation
                    
                    # Clean up the translated text
                    translated_text = translated_text.strip()
                    
                    # Remove common prefixes that might appear in the response
                    prefixes_to_remove = [
                        "Ecco la traduzione in italiano del testo fornito, mantenendo il significato originale:",
                        "Ecco la traduzione in italiano, mantenendo il significato originale:",
                        "Ecco la traduzione:",
                        "Traduzione:",
                        "Here's the translation:",
                        "Translation:",
                        "null"
                    ]
                    
                    for prefix in prefixes_to_remove:
                        if translated_text.lower().startswith(prefix.lower()):
                            translated_text = translated_text[len(prefix):].strip()
                    
                    # Assign translation to this specific block only
                    block.translation = translated_text
                    print(f"[DEBUG] Qwen Translator - Traduzione blocco {i+1}: {translated_text}")
                    
                else:
                    print(f"[ERROR] Unexpected response format from Qwen API for block {i+1}")
                    block.translation = ""
                            
            except Exception as e:
                print(f"Qwen translation error for block {i+1}: {str(e)}")
                block.translation = ""
            
            # Aggiunge un breve ritardo per evitare limiti di rate
            import time
            time.sleep(0.5)
                
        return blk_list
            
    @staticmethod
    def verify_api_key(api_key: str) -> bool:
        """
        Verify if the API key is valid by making a test request.
        
        Args:
            api_key: OpenRouter API key to verify
            
        Returns:
            True if the API key is valid, False otherwise
        """
        try:
            headers = {
                "Authorization": f"Bearer {api_key['api_key'].strip()}",
                "Content-Type": "application/json"
            }
            
            # Simple request to check API key validity
            response = requests.get("https://openrouter.ai/api/v1/auth/key", headers=headers)
            
            # Return True if the request was successful
            return response.status_code == 200
        except Exception:
            return False


class Qwen25VLTranslation(QwenTranslation):
    """Translation engine using Qwen2.5 VL 72B Instruct free model via OpenRouter API."""
    
    def __init__(self):
        """Initialize Qwen2.5 VL 72B Instruct free translation engine."""
        super().__init__(model_name="qwen/qwen2.5-vl-72b-instruct:free")
        
    def initialize(self, settings, source_lang: str, target_lang: str, model_type: str = "", **kwargs):
        """
        Initialize Qwen2.5 VL 72B free translation with API key and parameters.
        
        Args:
            settings: Application settings object
            source_lang: Source language
            target_lang: Target language
            model_type: Model type (not used for Qwen)
            **kwargs: Additional parameters
        """
        # Inizializziamo la classe base correttamente
        super().__init__(model_name="qwen/qwen2.5-vl-72b-instruct:free")
        
        # Set language attributes
        self.source_lang = source_lang
        self.target_lang = target_lang
        
        # Get API key from settings
        self.api_key = settings.get_credentials("Qwen2.5 VL 72B Instruct (free)")
        print(f"[DEBUG] Got API key for Qwen2.5 VL 72B Instruct (free): {self.api_key}")
        print(f"[DEBUG] Source language: {source_lang}, Target language: {target_lang}")
        
        # Get custom prompt if available
        custom_prompt = settings.get_qwen_translate_prompt()
        if custom_prompt:
            self.prompt = custom_prompt
            
        # Check if we should include image
        self.include_image = settings.get_value("include_image_in_llm", True)


class Qwen25VLPaidTranslation(QwenTranslation):
    """Translation engine using Qwen2.5 VL 72B Instruct paid model via OpenRouter API."""
    
    def __init__(self):
        """Initialize Qwen2.5 VL 72B Instruct paid translation engine."""
        super().__init__(model_name="qwen/qwen2.5-vl-72b-instruct")
        
    def initialize(self, settings, source_lang: str, target_lang: str, model_type: str = "", **kwargs):
        """
        Initialize Qwen2.5 VL 72B paid translation with API key and parameters.
        
        Args:
            settings: Application settings object
            source_lang: Source language
            target_lang: Target language
            model_type: Model type (not used for Qwen)
            **kwargs: Additional parameters
        """
        # Inizializziamo la classe base correttamente
        super().__init__(model_name="qwen/qwen2.5-vl-72b-instruct")
        
        # Set language attributes
        self.source_lang = source_lang
        self.target_lang = target_lang
        
        # Get API key from settings
        self.api_key = settings.get_credentials("Qwen2.5 VL 72B Instruct")
        print(f"[DEBUG] Got API key for Qwen2.5 VL 72B Instruct: {self.api_key}")
        
        # Get custom prompt if available
        custom_prompt = settings.get_qwen_translate_prompt()
        if custom_prompt:
            self.prompt = custom_prompt
            
        # Check if we should include image
        self.include_image = settings.get_value("include_image_in_llm", True)


class QwenVLPlus(LLMTranslation):
    """
    Qwen-Max translation engine.
    """

    def __init__(self, settings):
        super().__init__(settings)
        # Inizializzazione specifica per Qwen-Max
        self.model_name = 'Qwen-Max'
        self.api_key = self.get_credentials()  # Recupera la chiave API

    def translate(self, text, source_lang, target_lang):
        """
        Invia una richiesta di traduzione all'API Qwen-Max e restituisce la traduzione.
        """
        try:
            # Costruzione della richiesta
            headers = {'Authorization': f'Bearer {self.api_key["api_key"].strip()}', 'Content-Type': 'application/json'}
            payload = {
                'text': text,
                'source_lang': source_lang,
                'target_lang': target_lang
            }
            print(f"[DEBUG] Using API Key for Qwen Max: {self.api_key}")
            print(f"[DEBUG] API Headers: {headers}")
            print(f"[DEBUG] API Payload: {json.dumps(payload)}")
            response = requests.post('https://api.qwen.com/v1/translate', headers=headers, json=payload)

            # Controllo della risposta
            if response.status_code == 200:
                result = response.json()
                translation = result['choices'][0]['message']['content']
                
                # Se la risposta è in formato JSON, estrarre il contenuto della traduzione
                if translation.startswith("{") and "translation" in translation:
                    try:
                        json_response = json.loads(translation)
                        if isinstance(json_response, dict) and "translation" in json_response:
                            # Sostituisce le virgolette escapate con quelle normali
                            return json_response["translation"].replace('\\"', '"')
                    except json.JSONDecodeError:
                        # In caso di errore di parsing JSON, passa al return originale
                        pass
                
                # Se non è in formato JSON o c'è stato un errore di parsing, restituisce il testo così com'è
                return translation
            else:
                print(f'Error: {response.status_code} - {response.text}')  # Log dell'errore
                return None
        except Exception as e:
            print(f'Exception occurred: {str(e)}')  # Log dell'eccezione
            return None
