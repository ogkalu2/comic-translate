import pytest, time
from pipeline.cache_v2 import TranslationCacheV2, TranslationStatus

def test_empty_cache_has_version():
    c = TranslationCacheV2()
    assert c.data["version"] == "2.0"

def test_store_and_retrieve_success():
    c = TranslationCacheV2()
    c.store("en", "zh-hk", "Hello", "你好", model="gpt-4o-mini")
    result = c.get("en", "zh-hk", "Hello")
    assert result == "你好"

def test_api_failed_entry_not_served():
    c = TranslationCacheV2()
    c.store("en", "zh-hk", "Hello", "Hello",
            status=TranslationStatus.API_FAILED)
    result = c.get("en", "zh-hk", "Hello")
    assert result is None

def test_source_equals_target_stored_as_untranslatable():
    c = TranslationCacheV2()
    c.store("en", "zh-hk", "Eren", "Eren")
    entry = c._get_entry("en", "zh-hk", "Eren")
    assert entry["translation_status"] == TranslationStatus.UNTRANSLATABLE.value

def test_usage_count_increments():
    c = TranslationCacheV2()
    c.store("en", "zh-hk", "Hi", "嗨")
    c.get("en", "zh-hk", "Hi")
    c.get("en", "zh-hk", "Hi")
    entry = c._get_entry("en", "zh-hk", "Hi")
    assert entry["usage_count"] == 2

def test_migrate_v1_flat_cache():
    from pipeline.cache_v2 import migrate_v1_to_v2
    old = {"Hello": "你好", "Eren": "Eren"}
    new = migrate_v1_to_v2(old, src="en", tgt="zh-hk")
    assert new["version"] == "2.0"
    assert new["entries"]["en:zh-hk:Hello"]["translation_status"] == "success"
    assert new["entries"]["en:zh-hk:Eren"]["translation_status"] == "untranslatable"
