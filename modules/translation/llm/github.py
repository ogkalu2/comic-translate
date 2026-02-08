import os
from openai import OpenAI
from modules.translation.base import LLMTranslation

class GithubModelTranslation(LLMTranslation):
    """Translation engine using GitHub Models (OpenAI-compatible API)."""
    def __init__(self):
        super().__init__()
        self.model_name = None
        self.api_key = None
        self.api_base_url = "https://models.github.ai/inference"
        self.supports_images = False

    def initialize(self, settings, source_lang: str, target_lang: str, model_name: str = "", **kwargs):
        super().initialize(settings, source_lang, target_lang)
        self.model_name = model_name or "openai/gpt-5"
        credentials = settings.get_credentials(settings.ui.tr('GitHub'))
        self.api_key = credentials.get('api_key', os.environ.get("GITHUB_TOKEN", ""))

    def _perform_translation(self, user_prompt: str, system_prompt: str, image=None) -> str:
        client = OpenAI(
            base_url=self.api_base_url,
            api_key=self.api_key,
        )
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model=self.model_name
        )
        content = response.choices[0].message.content
        return content if content is not None else ""
