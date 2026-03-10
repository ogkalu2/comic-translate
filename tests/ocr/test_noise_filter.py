import pytest
from modules.ocr.noise_filter import OCRNoiseFilter, NoiseType

def test_phantom_symbol_run_detected():
    f = OCRNoiseFilter()
    # CJK chars are preserved; garbage digits+symbols are stripped
    result = f.filter_text('21,"0~(!!"')
    assert result.strip() == ""

def test_clean_text_passes():
    f = OCRNoiseFilter()
    result = f.filter_text("Hello world")
    assert result == "Hello world"

def test_low_confidence_token_flagged():
    f = OCRNoiseFilter()
    tokens = [("Hello", 0.9), ("world", 0.3)]
    clean = f.filter_tokens(tokens, threshold=0.4)
    assert clean == ["Hello"]

def test_misread_punctuation_cleaned():
    f = OCRNoiseFilter()
    result = f.filter_text("%.")
    assert result == ""
