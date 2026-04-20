from types import SimpleNamespace

from pipeline.translation_context import (
    build_translation_prompt_context,
    store_page_translation_context,
)


def test_build_translation_prompt_context_includes_previous_page_snapshot_and_scene_memory():
    main_page = SimpleNamespace(
        image_files=["page-1.png", "page-2.png"],
        image_states={
            "page-1.png": {
                "translation_context": {
                    "English": {
                        "page_snapshot": "- src: ありがとう\n  trg: Thanks.",
                        "scene_memory": "Two friends soften after an argument.",
                    }
                }
            }
        },
    )

    prompt_context, cache_signature = build_translation_prompt_context(
        main_page,
        "page-2.png",
        "English",
        llm_settings={
            "extra_context": "Keep names consistent.",
            "use_previous_page_context": True,
            "use_scene_memory": True,
            "previous_page_lines": 4,
        },
    )

    assert "Keep names consistent." in prompt_context
    assert "Previous page dialogue tail" in prompt_context
    assert "Thanks." in prompt_context
    assert "Two friends soften after an argument." in prompt_context
    assert '"use_previous_page_context":true' in cache_signature


def test_store_page_translation_context_keeps_target_specific_snapshot_and_memory():
    image_states = {}
    blocks = [
        SimpleNamespace(text="やめて", translation="Stop it."),
        SimpleNamespace(text="ごめん", translation="Sorry."),
    ]

    store_page_translation_context(
        image_states,
        "page-1.png",
        "English",
        blocks,
        scene_memory="A tense exchange ends with an apology.",
        llm_settings={"previous_page_lines": 2},
    )

    entry = image_states["page-1.png"]["translation_context"]["English"]
    assert "Stop it." in entry["page_snapshot"]
    assert entry["scene_memory"] == "A tense exchange ends with an apology."
