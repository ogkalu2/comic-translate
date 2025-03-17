import unittest
from unittest.mock import MagicMock, patch
from modules.translator.llm.deepseek import DeepseekTranslation
from modules.utils.textblock import TextBlock
from openai import OpenAI

class TestDeepseekTranslation():
    def __init__(self):
        self.translator = DeepseekTranslation()

    def test_perform_translation(self):
        # 初始化翻译器
        self.translator.client = OpenAI(api_key="sk-91043ea797ae460680043f6964239dc1", base_url="https://api.deepseek.com/v1")

        # 执行翻译
        result = self.translator._perform_translation(
            'Test text',
            'Translate to Chinese',
            None
        )

        # 验证翻译结果
        print(result)

if __name__ == '__main__':
    trans = TestDeepseekTranslation()
    trans.test_perform_translation()