from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QT_TRANSLATE_NOOP


@dataclass(frozen=True)
class ShortcutDefinition:
    id: str
    label: str
    description: str
    default: str


SHORTCUT_DEFINITIONS: tuple[ShortcutDefinition, ...] = (
    ShortcutDefinition(
        id="save_project",
        label=QT_TRANSLATE_NOOP("ShortcutDefinitions", "Save Project"),
        description=QT_TRANSLATE_NOOP("ShortcutDefinitions", "Save the current project file."),
        default="Ctrl+S",
    ),
    ShortcutDefinition(
        id="save_current_image",
        label=QT_TRANSLATE_NOOP("ShortcutDefinitions", "Save Current Image"),
        description=QT_TRANSLATE_NOOP("ShortcutDefinitions", "Save the currently loaded image."),
        default="Ctrl+E",
    ),
    ShortcutDefinition(
        id="undo",
        label=QT_TRANSLATE_NOOP("ShortcutDefinitions", "Undo"),
        description=QT_TRANSLATE_NOOP("ShortcutDefinitions", "Undo the last editing action."),
        default="Ctrl+Z",
    ),
    ShortcutDefinition(
        id="redo",
        label=QT_TRANSLATE_NOOP("ShortcutDefinitions", "Redo"),
        description=QT_TRANSLATE_NOOP("ShortcutDefinitions", "Redo the previously undone action."),
        default="Ctrl+Y",
    ),
    ShortcutDefinition(
        id="delete_selected_box",
        label=QT_TRANSLATE_NOOP("ShortcutDefinitions", "Delete Selected Box"),
        description=QT_TRANSLATE_NOOP("ShortcutDefinitions", "Delete the currently selected text box."),
        default="Delete",
    ),
    ShortcutDefinition(
        id="restore_text_blocks",
        label=QT_TRANSLATE_NOOP("ShortcutDefinitions", "Restore Text Blocks"),
        description=QT_TRANSLATE_NOOP("ShortcutDefinitions", "Draw saved text blocks back onto the image for editing."),
        default="Ctrl+Shift+R",
    ),
    ShortcutDefinition(
        id="toggle_brush_strokes",
        label=QT_TRANSLATE_NOOP("ShortcutDefinitions", "Toggle Brush Strokes"),
        description=QT_TRANSLATE_NOOP("ShortcutDefinitions", "Toggle brush stroke drawing on or off."),
        default="Ctrl+D",
    ),
)


def get_shortcut_definitions() -> tuple[ShortcutDefinition, ...]:
    return SHORTCUT_DEFINITIONS


def get_default_shortcuts() -> dict[str, str]:
    return {definition.id: definition.default for definition in SHORTCUT_DEFINITIONS}
