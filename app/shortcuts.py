from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ShortcutDefinition:
    id: str
    label: str
    description: str
    default: str


SHORTCUT_DEFINITIONS: tuple[ShortcutDefinition, ...] = (
    ShortcutDefinition(
        id="undo",
        label="Undo",
        description="Undo the last editing action.",
        default="Ctrl+Z",
    ),
    ShortcutDefinition(
        id="redo",
        label="Redo",
        description="Redo the previously undone action.",
        default="Ctrl+Y",
    ),
    ShortcutDefinition(
        id="delete_selected_box",
        label="Delete Selected Box",
        description="Delete the currently selected text box.",
        default="Delete",
    ),
    ShortcutDefinition(
        id="restore_text_blocks",
        label="Restore Text Blocks",
        description="Draw saved text blocks back onto the image for editing.",
        default="Ctrl+Shift+R",
    ),
)


def get_shortcut_definitions() -> tuple[ShortcutDefinition, ...]:
    return SHORTCUT_DEFINITIONS


def get_default_shortcuts() -> dict[str, str]:
    return {definition.id: definition.default for definition in SHORTCUT_DEFINITIONS}
