from contextlib import contextmanager
from tempfile import NamedTemporaryFile

from requests import get


def postprocess_span(tagger, text: str) -> str:
    """
    Postprocess NOUN span to remove unnecessary character

    Args:
        text (str): NOUN span to be processed

    Returns:
        (str): post-processed NOUN span

    Examples:
        >>> postprocess_span("강감찬 장군은")
        '강감찬 장군'
        >>> postprocess_span("그녀에게")
        '그녀'

    """

    # First, strip punctuations
    text = text.strip("""!"\#$&'()*+,\-./:;<=>?@\^_‘{|}~《》""")

    # Complete imbalanced parentheses pair
    if text.count("(") == text.count(")") + 1:
        text += ")"
    elif text.count("(") + 1 == text.count(")"):
        text = "(" + text

    # Preserve beginning tokens since we only want to extract noun phrase of the last eojeol
    noun_phrase = " ".join(text.rsplit(" ", 1)[:-1])
    tokens = text.split(" ")
    eojeols = list()
    for token in tokens:
        eojeols.append(tagger.pos(token))
    last_eojeol = eojeols[-1]

    # Iterate backwardly to remove unnecessary postfixes
    i = 0
    for i, token in enumerate(last_eojeol[::-1]):
        _, pos = token
        # 1. The loop breaks when you meet a noun
        # 2. The loop also breaks when you meet a XSN (e.g. 8/SN+일/NNB LG/SL 전/XSN)
        if (pos[0] in ("N", "S")) or pos.startswith("XSN"):
            break
    idx = len(last_eojeol) - i

    # Extract noun span from last eojeol and postpend it to beginning tokens
    ext_last_eojeol = "".join(morph for morph, _ in last_eojeol[:idx])
    noun_phrase += " " + ext_last_eojeol
    return noun_phrase.strip()


@contextmanager
def control_temp(file_path: str):
    """
    Download temporary file from web, then remove it after some context

    Args:
        file_path (str): web file path

    """
    # yapf: disable
    assert file_path.startswith("http"), "File path should contain `http` prefix !"
    # yapf: enable

    ext = file_path[file_path.rfind("."):]

    with NamedTemporaryFile("wb", suffix=ext, delete=True) as f:
        response = get(file_path, allow_redirects=True)
        f.write(response.content)
        yield f.name
