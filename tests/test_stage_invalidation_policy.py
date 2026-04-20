from pipeline.invalidation_policy import invalidate_page_for_format_edit
from pipeline.stage_state import is_stage_available


def test_format_edit_keeps_render_stage_current_and_valid():
    state = {
        "target_lang": "English",
        "pipeline_state": {
            "target_lang": "English",
            "current_stage": "render",
            "target_validity": {
                "English": {
                    "translate": True,
                    "render": True,
                }
            },
        },
        "target_render_states": {
            "English": {
                "text_items_state": [
                    {
                        "block_uid": "title",
                        "text": "Hello",
                    }
                ]
            }
        },
    }

    updated_state, ui_stage = invalidate_page_for_format_edit(
        {"page.png": state},
        {},
        "page.png",
        "English",
    )

    assert updated_state is state
    assert ui_stage == "render"
    assert state["ui_stage"] == "render"
    assert state["pipeline_state"]["current_stage"] == "render"
    assert state["pipeline_state"]["target_validity"]["English"]["render"] is True


def test_legacy_detection_only_state_infers_saved_render_readiness():
    class Block:
        text = "source"
        translation = "target"
        block_uid = "title"

    state = {
        "target_lang": "English",
        "blk_list": [Block()],
        "pipeline_state": {
            "target_lang": "English",
            "completed_stages": ["detection"],
        },
        "target_render_states": {
            "English": {
                "text_items_state": [
                    {
                        "block_uid": "title",
                        "text": "target",
                    }
                ]
            }
        },
    }

    assert is_stage_available(state, "ocr", target_lang="English")
    assert is_stage_available(state, "translate", target_lang="English")
    assert is_stage_available(state, "render", target_lang="English")
