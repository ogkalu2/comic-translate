"""Run from the repository root: python -m unittest discover -s tests -v."""

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PySide6 import QtWidgets
from PySide6.QtCore import QSettings

from app.ui.settings.llms_page import LlmsPage
from modules.translation.base import TraditionalTranslation
from modules.translation.llm.custom import CustomTranslation
from modules.translation.presets import BUILTIN_GLOSSARIES, TRANSLATION_STYLES, build_extra_context, parse_glossary
from modules.translation.processor import Translator
from modules.translation.user import UserTranslator
from modules.utils.textblock import TextBlock
from pipeline.cache_manager import CacheManager
from pipeline.translation_handler import TranslationHandler


class TranslationPresetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        settings_path = str(Path(self.temp.name) / "settings.ini")
        settings_class = patch("app.ui.settings.llms_page.QtCore.QSettings",
            side_effect=lambda *args: QSettings(settings_path, QSettings.Format.IniFormat))
        mocked = settings_class.start()
        mocked.Status = QSettings.Status
        self.addCleanup(settings_class.stop)
        self.page = LlmsPage()
        self.addCleanup(self.page.close)
        self.warning = patch.object(QtWidgets.QMessageBox, "warning").start()
        self.addCleanup(patch.stopall)
        self.question = patch.object(QtWidgets.QMessageBox, "question",
            return_value=QtWidgets.QMessageBox.StandardButton.No).start()

    def select_preset(self, index=1, style="natural"):
        self.page.glossary_combo.setCurrentIndex(index)
        self.page.style_combo.setCurrentIndex(self.page.style_combo.findData(style))

    def import_json(self, content):
        path = Path(self.temp.name) / "glossary.json"
        path.write_text(content, encoding="utf-8-sig")
        with patch.object(QtWidgets.QFileDialog, "getOpenFileName", return_value=(str(path), "")):
            self.page.import_glossary_button.click()

    def settings(self, translator):
        return SimpleNamespace(
            ui=SimpleNamespace(tr=lambda text: text), auth_client=Mock(),
            get_tool_selection=lambda tool: translator,
            get_llm_settings=lambda: {"extra_context": self.page.extra_context.toPlainText(), "image_input_enabled": True},
            get_credentials=lambda service: {"api_key": "test-only", "model": "test-model", "api_url": "https://example.invalid/v1"},
        )

    def test_builtin_regions_and_budget(self):
        self.assertEqual([item["terms"]["Iron Man"] for item in BUILTIN_GLOSSARIES], ["钢铁侠", "鋼鐵人", "鐵甲奇俠"])
        self.assertEqual([item["terms"]["Peter Parker"] for item in BUILTIN_GLOSSARIES], ["彼得·帕克", "彼得帕克", "彼得柏加"])
        for glossary in BUILTIN_GLOSSARIES:
            self.assertEqual(parse_glossary(json.dumps(glossary)), glossary)
            for style in TRANSLATION_STYLES:
                self.assertLessEqual(len(build_extra_context(glossary, style)), 1000)
        self.assertEqual(build_extra_context(None), "")
        self.assertIn("do not invent", build_extra_context(None, "natural"))
        self.assertIn("original tone", build_extra_context(None, "faithful"))

    def test_import_validation(self):
        valid = {"name": "My comic", "source_language": "English", "target_language": "French", "terms": {"Alice": "Alix"}}
        self.assertEqual(parse_glossary(json.dumps(valid)), valid)
        for invalid in ("{", "[]", "null", "{}", json.dumps({**valid, "name": 1}),
                        json.dumps({**valid, "source_language": " "}), json.dumps({**valid, "target_language": False}),
                        json.dumps({**valid, "terms": {}}), json.dumps({**valid, "terms": []}),
                        json.dumps({**valid, "terms": {"Alice": None}}), json.dumps({**valid, "terms": {" ": "Alix"}}),
                        json.dumps({**valid, "terms": {"Alice": "Alix", " Alice ": "Alice"}}),
                        '{"name":"A","name":"B"}',
                        '{"name":"A","source_language":"English","target_language":"French","terms":{"Alice":"A","Alice":"B"}}'):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                parse_glossary(invalid)

    def test_apply_and_cancel_replacement(self):
        self.assertFalse(self.page.apply_preset_button.isEnabled())
        self.select_preset()
        expected = self.page._preset_context()
        self.page.apply_preset_button.click()
        self.assertEqual(self.page.extra_context.toPlainText(), expected)
        self.question.assert_not_called()
        self.page.extra_context.setPlainText("Keep my own instructions.")
        self.page.apply_preset_button.click()
        self.assertEqual(self.page.extra_context.toPlainText(), "Keep my own instructions.")
        self.question.return_value = QtWidgets.QMessageBox.StandardButton.Yes
        self.page.apply_preset_button.click()
        self.assertEqual(self.page.extra_context.toPlainText(), expected)
        self.question.reset_mock()
        self.page.apply_preset_button.click()
        self.question.assert_not_called()

    def test_exact_limit_and_custom(self):
        glossary = {**BUILTIN_GLOSSARIES[0], "name": "Large glossary", "terms": {"Alice": ""}}
        overhead = len(build_extra_context(glossary))
        for size in (1000, 1001):
            glossary["terms"]["Alice"] = "字" * (size - overhead)
            self.page.glossary_combo.addItem("Large glossary", glossary)
            self.page.glossary_combo.setCurrentIndex(self.page.glossary_combo.count() - 1)
            self.assertEqual(len(self.page._preset_context()), size)
            self.page.extra_context.clear()
            self.page.apply_preset_button.click()
            self.assertEqual(len(self.page.extra_context.toPlainText()), size if size == 1000 else 0)
        self.warning.assert_called_once()
        self.page.set_extra_context_unlimited(True)
        self.page.apply_preset_button.click()
        self.assertEqual(len(self.page.extra_context.toPlainText()), 1001)

    def test_import_persists_and_replacement_can_be_cancelled(self):
        glossary = {**BUILTIN_GLOSSARIES[0], "name": "My comic"}
        self.import_json(json.dumps(glossary))
        self.assertEqual(self.page.glossary_combo.currentData(), glossary)
        self.assertEqual(self.page.extra_context.toPlainText(), "")
        restarted = LlmsPage()
        self.addCleanup(restarted.close)
        self.assertEqual(restarted.glossary_combo.itemData(restarted.glossary_combo.count() - 1), glossary)
        before = self.page._glossary_settings.value("translation_glossaries")
        replacement = {**glossary, "terms": {"Iron Man": "My preferred name"}}
        self.import_json(json.dumps(replacement))
        self.assertEqual(self.page._glossary_settings.value("translation_glossaries"), before)
        self.question.return_value = QtWidgets.QMessageBox.StandardButton.Yes
        self.import_json(json.dumps(replacement))
        self.assertEqual(self.page.glossary_combo.currentData(), replacement)
        self.assertEqual(self.page.glossary_combo.count(), 5)

    def test_failed_import_preserves_data(self):
        self.import_json(json.dumps({**BUILTIN_GLOSSARIES[0], "name": "My comic"}))
        before = self.page._glossary_settings.value("translation_glossaries")
        current = self.page.glossary_combo.currentData()
        self.page.extra_context.setPlainText("Unchanged")
        for content in ("{", json.dumps(BUILTIN_GLOSSARIES[0])):
            self.import_json(content)
            self.assertEqual(self.page._glossary_settings.value("translation_glossaries"), before)
            self.assertEqual(self.page.glossary_combo.currentData(), current)
            self.assertEqual(self.page.extra_context.toPlainText(), "Unchanged")
        self.assertEqual(self.warning.call_count, 2)

    def test_account_llm_request_contains_image_and_context(self):
        self.select_preset()
        self.page.apply_preset_button.click()
        context = self.page.extra_context.toPlainText()
        for key in ("GPT-4.1", "Claude-4.6-Sonnet", "Gemini-3.1-Flash-Lite", "Deepseek", "DeepL"):
            with self.subTest(translator=key):
                settings = self.settings(key)
                engine = UserTranslator()
                engine.initialize(settings, "English", "Simplified Chinese", key)
                response = Mock(status_code=200)
                response.json.return_value = {"translations": [{"id": 0, "translation": "蜘蛛侠，等等！"}]}
                blocks = [TextBlock(text="Spider-Man, wait for Tony Stark!")]
                with patch("modules.translation.processor.TranslationFactory.create_engine", return_value=engine), \
                     patch.object(engine, "_get_access_token", return_value="test-only"), \
                     patch.object(engine._session, "post", return_value=response) as post:
                    translator = Translator(SimpleNamespace(settings_page=settings, lang_mapping={}), "English", "Simplified Chinese")
                    translator.translate(blocks, np.zeros((2, 2, 3), dtype=np.uint8), context)
                payload = post.call_args.kwargs["json"]
                self.assertEqual(blocks[0].translation, "蜘蛛侠，等等！")
                if key == "DeepL":
                    self.assertNotIn("extra_context", payload)
                    self.assertNotIn("image_base64", payload)
                else:
                    self.assertEqual(payload["extra_context"], context)
                    self.assertTrue(payload["image_base64"])

    def test_custom_request_preserves_output_contract(self):
        self.select_preset()
        self.page.apply_preset_button.click()
        context = self.page.extra_context.toPlainText()
        settings = self.settings("Custom")
        engine = CustomTranslation()
        engine.initialize(settings, "English", "Simplified Chinese", "Custom")
        response = Mock()
        response.json.return_value = {"choices": [{"message": {"content": '{"block_0":"蜘蛛侠，等等！"}'}}]}
        with patch("modules.translation.processor.TranslationFactory.create_engine", return_value=engine), \
             patch("modules.translation.llm.gpt.requests.post", return_value=response) as post:
            translator = Translator(SimpleNamespace(settings_page=settings, lang_mapping={}), "English", "Simplified Chinese")
            blocks = [TextBlock(text="Spider-Man, wait for Tony Stark!")]
            translator.translate(blocks, np.zeros((2, 2, 3), dtype=np.uint8), context)
        payload = json.loads(post.call_args.kwargs["data"])
        self.assertIn(context, payload["messages"][1]["content"][0]["text"])
        self.assertIn("DO NOT translate the keys", payload["messages"][0]["content"][0]["text"])
        self.assertEqual(payload["messages"][1]["content"][1]["type"], "image_url")
        self.assertEqual(blocks[0].translation, "蜘蛛侠，等等！")

    def test_traditional_dispatch_and_empty_blocks(self):
        engine = Mock(spec=TraditionalTranslation)
        settings = self.settings("DeepL")
        with patch("modules.translation.processor.TranslationFactory.create_engine", return_value=engine):
            translator = Translator(SimpleNamespace(settings_page=settings, lang_mapping={}), "English", "French")
        blank = TextBlock(text="...", translation="old")
        blocks = [TextBlock(text="Hello"), blank]
        translator.translate(blocks, None, "Extra context")
        engine.translate.assert_called_once_with([blocks[0]])
        self.assertEqual(blank.translation, "")
        engine.translate.reset_mock()
        translator.translate([blank])
        engine.translate.assert_not_called()

    def test_context_changes_cache_key(self):
        image = np.zeros((2, 2, 3), dtype=np.uint8)
        cache = CacheManager()
        contexts = [build_extra_context(glossary, style) for glossary in BUILTIN_GLOSSARIES for style in TRANSLATION_STYLES]
        keys = [cache._get_translation_cache_key(image, "English", "Traditional Chinese", "Custom", ctx) for ctx in contexts]
        self.assertEqual(len(set(keys)), len(keys))

    def test_project_round_trip_keeps_applied_context(self):
        from app.controllers.projects import ProjectController
        from app.projects.project_state import save_state_to_proj_file, load_state_from_proj_file, close_state_store
        from PIL import Image

        self.select_preset()
        self.page.apply_preset_button.click()
        context = self.page.extra_context.toPlainText()
        image_path = str(Path(self.temp.name) / "page.png")
        Image.new("RGB", (20, 20), "white").save(image_path)
        main = SimpleNamespace(
            settings_page=self.settings("Custom"), curr_img_idx=0, image_files=[image_path],
            image_states={image_path: {}}, current_history_index={}, displayed_images=set(), loaded_images=[],
            image_data={}, in_memory_history={}, image_history={}, image_patches={}, webtoon_mode=False,
            image_viewer=SimpleNamespace(webtoon_view_state={}), temp_dir=str(Path(self.temp.name) / "loaded"),
        )
        main.settings_page.ui.extra_context = self.page.extra_context
        project_path = str(Path(self.temp.name) / "comic.ctpr")
        self.addCleanup(close_state_store, project_path)
        save_state_to_proj_file(main, project_path)
        self.page.extra_context.clear()
        restored = load_state_from_proj_file(main, project_path)
        ProjectController.load_state_to_ui(SimpleNamespace(main=main), restored)
        self.assertEqual(self.page.extra_context.toPlainText(), context)

    def test_page_single_block_and_visible_webtoon_forward_context(self):
        self.select_preset()
        self.page.apply_preset_button.click()
        context = self.page.extra_context.toPlainText()
        image = np.zeros((20, 20, 3), dtype=np.uint8)
        block = TextBlock(text="Spider-Man, wait!", text_bbox=np.array([0, 0, 10, 10]))
        settings = self.settings("Custom")
        settings.ui.uppercase_checkbox = Mock()
        settings.ui.uppercase_checkbox.isChecked.return_value = False
        main = SimpleNamespace(settings_page=settings, lang_mapping={}, blk_list=[block], webtoon_mode=True,
            s_combo=Mock(), t_combo=Mock(), image_viewer=Mock())
        main.s_combo.currentText.return_value = "English"
        main.t_combo.currentText.return_value = "Simplified Chinese"
        main.image_viewer.hasPhoto.return_value = True
        main.image_viewer.get_image_array.return_value = image
        main.image_viewer.get_visible_area_image.return_value = (image, ["mapping"])
        pipeline = SimpleNamespace(get_selected_block=lambda: block)
        cache = CacheManager()
        handler = TranslationHandler(main, cache, pipeline)
        translator = Mock()
        translator.translate.side_effect = lambda blocks, *args: [setattr(item, "translation", "translated") for item in blocks]
        with patch("pipeline.translation_handler.Translator", return_value=translator):
            handler.translate_image()
            self.assertEqual(translator.translate.call_args.args[2], context)
            handler.translate_image()
            self.assertEqual(translator.translate.call_count, 1)
            self.page.extra_context.setPlainText(context + "\nKeep exclamations.")
            handler.translate_image()
            self.assertEqual(translator.translate.call_count, 2)
            block.translation = ""
            cache.clear_translation_cache()
            handler.translate_image(single_block=True)
            self.assertEqual([item.text for item in translator.translate.call_args.args[0]], [block.text])
            self.assertEqual(block.translation, "translated")
            self.assertEqual(translator.translate.call_args.args[2], self.page.extra_context.toPlainText())
            with patch("pipeline.translation_handler.filter_and_convert_visible_blocks", return_value=[block]), \
                 patch("pipeline.translation_handler.restore_original_block_coordinates"):
                handler.translate_webtoon_visible_area()
            self.assertEqual(translator.translate.call_args.args[2], self.page.extra_context.toPlainText())

    def test_batch_and_webtoon_chunk_forward_context(self):
        from pipeline.batch_processor import BatchProcessor
        from pipeline.webtoon_batch.chunk import ChunkMixin

        self.select_preset()
        self.page.apply_preset_button.click()
        context = self.page.extra_context.toPlainText()
        image = np.zeros((20, 20, 3), dtype=np.uint8)
        block = TextBlock(text="Spider-Man, wait!", text_bbox=np.array([0, 0, 10, 10]))
        path = str(Path(self.temp.name) / "page.png")
        settings = self.settings("Custom")
        settings.is_gpu_enabled = lambda: False
        main = SimpleNamespace(settings_page=settings, image_files=[path], curr_img_idx=0, blk_list=[block],
            image_states={path: {"source_lang": "English", "target_lang": "Simplified Chinese"}},
            file_handler=SimpleNamespace(archive_info=[]), current_worker=SimpleNamespace(is_cancelled=False),
            progress_update=Mock(), image_skipped=Mock())
        detection = Mock()
        detection.block_detector_cache.detect.return_value = [block]
        processor = BatchProcessor(main, CacheManager(), detection, Mock(), Mock())
        translator = Mock()
        def translate(blocks, image, extra_context):
            blocks[0].translation = "translated"
            main.current_worker.is_cancelled = True
        translator.translate.side_effect = translate
        with patch("pipeline.batch_processor.Translator", return_value=translator), \
             patch("pipeline.batch_processor.imk.read_image", return_value=image), \
             patch("pipeline.batch_processor.ensure_path_materialized"):
            processor.batch_process()
        self.assertEqual(translator.translate.call_args.args[2], context)
        main.image_skipped.emit.assert_not_called()
        with patch("pipeline.webtoon_batch.chunk.Translator", return_value=translator):
            ChunkMixin._run_translation_on_blocks(SimpleNamespace(main_page=main), image, [block], "English", "Simplified Chinese", path)
        self.assertEqual(translator.translate.call_args.args[2], context)


if __name__ == "__main__":
    unittest.main()
