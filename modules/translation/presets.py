"""Small translation presets; localized name sources are listed in docs/translation_presets.md."""

import json


BUILTIN_GLOSSARIES = (
    {
        "name": "Marvel (Mainland China)",
        "source_language": "English",
        "target_language": "Simplified Chinese",
        "terms": {
            "Spider-Man": "蜘蛛侠", "Spider Man": "蜘蛛侠", "Peter Parker": "彼得·帕克",
            "Iron Man": "钢铁侠", "Tony Stark": "托尼·斯塔克", "Captain America": "美国队长",
            "Hulk": "绿巨人", "Black Widow": "黑寡妇", "Ant-Man": "蚁人",
        },
    },
    {
        "name": "Marvel (Taiwan)",
        "source_language": "English",
        "target_language": "Traditional Chinese",
        "terms": {
            "Spider-Man": "蜘蛛人", "Spider Man": "蜘蛛人", "Peter Parker": "彼得帕克",
            "Iron Man": "鋼鐵人", "Tony Stark": "東尼史塔克", "Captain America": "美國隊長",
            "Hulk": "浩克", "Black Widow": "黑寡婦", "Ant-Man": "蟻人",
        },
    },
    {
        "name": "Marvel (Hong Kong)",
        "source_language": "English",
        "target_language": "Traditional Chinese",
        "terms": {
            "Spider-Man": "蜘蛛俠", "Spider Man": "蜘蛛俠", "Peter Parker": "彼得柏加",
            "Iron Man": "鐵甲奇俠", "Tony Stark": "東尼史達", "Captain America": "美國隊長",
            "Hulk": "變形俠醫", "Black Widow": "黑寡婦", "Ant-Man": "蟻俠",
        },
    },
)

TRANSLATION_STYLES = {
    "none": "",
    "faithful": "Preserve the original tone, register, humor and character voices. Do not add or omit meaning.",
    "natural": "Use natural spoken dialogue in the target language. Preserve emotion, humor and distinct character voices; do not invent or omit meaning.",
}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key!r}")
        result[key] = value
    return result


def validate_glossary(data: dict) -> dict:
    """Validate imported or persisted data without modifying it."""
    if not isinstance(data, dict):
        raise ValueError("A glossary must be a JSON object.")
    result = {}
    for field in ("name", "source_language", "target_language"):
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} must be a non-empty string.")
        result[field] = value.strip()
    terms = data.get("terms")
    if not isinstance(terms, dict) or not terms:
        raise ValueError("terms must be a non-empty object of source names and translations.")
    result["terms"] = {}
    for source, target in terms.items():
        if not isinstance(source, str) or not source.strip() or not isinstance(target, str) or not target.strip():
            raise ValueError("Each source name and translation must be a non-empty string.")
        source = source.strip()
        if source in result["terms"]:
            raise ValueError(f"Duplicate source name: {source!r}")
        result["terms"][source] = target.strip()
    return result


def parse_glossary(text: str) -> dict:
    return validate_glossary(json.loads(text, object_pairs_hook=_unique_object))


def build_extra_context(glossary: dict | None, style: str = "none") -> str:
    """Generate editable context, leaving the translator's output contract intact."""
    parts = []
    if glossary is not None:
        parts.append(
            f"For {glossary['source_language']} to {glossary['target_language']}, "
            "use these name translations consistently. Keep hero and civilian names distinct:\n"
            + json.dumps(glossary["terms"], ensure_ascii=False, separators=(",", ":"))
        )
    if TRANSLATION_STYLES[style]:
        parts.append(TRANSLATION_STYLES[style])
    return "\n\n".join(parts)
