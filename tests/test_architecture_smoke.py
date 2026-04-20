from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

PYTHON_SOURCES = [
    REPO_ROOT / "app",
    REPO_ROOT / "pipeline",
    REPO_ROOT / "controller.py",
    REPO_ROOT / "comic.py",
    REPO_ROOT / "main.py",
]

REMOVED_MODULES = {
    "app.controllers.manual_workflow",
    "app.controllers.project_autosave_mixin",
    "app.controllers.stage_view_mixin",
    "app.controllers.image_navigation_mixin",
    "app.controllers.image_collection_mixin",
    "app.controllers.search_replace_navigation_mixin",
    "app.controllers.text_scene_mixin",
    "app.controllers.text_bulk_mixin",
    "app.controllers.text_bulk_actions_mixin",
    "pipeline.webtoon_batch.chunk",
    "pipeline.webtoon_batch.planning",
    "pipeline.webtoon_batch.render",
    "pipeline.webtoon_batch.render_state_mixin",
}

REMOVED_FILES = [
    REPO_ROOT / "app" / "controllers" / "manual_workflow.py",
    REPO_ROOT / "app" / "controllers" / "project_autosave_mixin.py",
    REPO_ROOT / "app" / "controllers" / "stage_view_mixin.py",
    REPO_ROOT / "app" / "controllers" / "image_navigation_mixin.py",
    REPO_ROOT / "app" / "controllers" / "image_collection_mixin.py",
    REPO_ROOT / "app" / "controllers" / "search_replace_navigation_mixin.py",
    REPO_ROOT / "app" / "controllers" / "text_scene_mixin.py",
    REPO_ROOT / "app" / "controllers" / "text_bulk_mixin.py",
    REPO_ROOT / "app" / "controllers" / "text_bulk_actions_mixin.py",
    REPO_ROOT / "pipeline" / "webtoon_batch" / "chunk.py",
    REPO_ROOT / "pipeline" / "webtoon_batch" / "planning.py",
    REPO_ROOT / "pipeline" / "webtoon_batch" / "render.py",
    REPO_ROOT / "pipeline" / "webtoon_batch" / "render_state_mixin.py",
]


def _iter_python_files():
    for source in PYTHON_SOURCES:
        if source.is_file():
            yield source
            continue
        for path in source.rglob("*.py"):
            if "__pycache__" not in path.parts:
                yield path


def _parse_python(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))


def _iter_imported_modules(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module


def test_removed_files_are_gone():
    present = [str(path.relative_to(REPO_ROOT)) for path in REMOVED_FILES if path.exists()]
    assert not present, f"Removed facade/legacy files reappeared: {present}"


def test_no_imports_of_removed_modules():
    violations: list[str] = []

    for path in _iter_python_files():
        tree = _parse_python(path)
        for module_name in _iter_imported_modules(tree):
            for removed in REMOVED_MODULES:
                if module_name == removed or module_name.startswith(f"{removed}."):
                    violations.append(f"{path.relative_to(REPO_ROOT)} imports {module_name}")

    assert not violations, "Removed facade/legacy modules are still imported:\n" + "\n".join(sorted(violations))


def test_no_empty_wrapper_modules():
    violations: list[str] = []
    checked_roots = {
        REPO_ROOT / "app" / "controllers",
        REPO_ROOT / "pipeline" / "webtoon_batch",
    }

    for root in checked_roots:
        for path in root.rglob("*.py"):
            if path.name == "__init__.py":
                continue
            tree = _parse_python(path)
            class_defs = [node for node in tree.body if isinstance(node, ast.ClassDef)]
            if len(class_defs) != 1:
                continue

            body = [
                node
                for node in class_defs[0].body
                if not (
                    isinstance(node, ast.Expr)
                    and isinstance(node.value, ast.Constant)
                    and isinstance(node.value.value, str)
                )
            ]
            if len(body) == 1 and isinstance(body[0], ast.Pass):
                violations.append(str(path.relative_to(REPO_ROOT)))

    assert not violations, "Empty wrapper modules should not exist:\n" + "\n".join(sorted(violations))


def test_no_manual_workflow_symbol_mentions():
    hits: list[str] = []
    needles = ("manual_workflow", "ManualWorkflowController")

    for path in _iter_python_files():
        text = path.read_text(encoding="utf-8-sig")
        for needle in needles:
            if needle in text:
                hits.append(f"{path.relative_to(REPO_ROOT)} contains {needle}")

    assert not hits, "Legacy manual workflow symbols should be absent:\n" + "\n".join(sorted(hits))
