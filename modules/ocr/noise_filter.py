import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Tuple, Optional

class NoiseType(Enum):
    PHANTOM = "ocr_noise.phantom"
    MISREAD = "ocr_noise.misread"

@dataclass
class NoiseEntry:
    original: str
    noise_type: NoiseType

# Regex: runs of 2+ non-alphanumeric, non-CJK, non-space chars
_SYMBOL_RUN = re.compile(r'[^\w\s\u3000-\u9fff\uff00-\uffef]{2,}')
# Regex: mixed symbol+digit garbage like 21,"0~(!!"
_GARBAGE = re.compile(r'\d+[,"\'\~\!\(\)\[\]]{2,}')

class OCRNoiseFilter:
    def filter_tokens(
        self,
        tokens: List[Tuple[str, float]],
        threshold: float = 0.4
    ) -> List[str]:
        """Drop tokens whose confidence is below threshold."""
        return [t for t, conf in tokens if conf >= threshold]

    def filter_text(self, text: str) -> str:
        """Remove phantom/misread noise patterns from raw OCR text."""
        text = _GARBAGE.sub("", text)
        text = _SYMBOL_RUN.sub("", text)
        return text.strip()

    def filter_block_text(
        self,
        text: str,
        tokens: Optional[List[Tuple[str, float]]] = None,
        confidence_threshold: float = 0.4
    ) -> Tuple[str, List[NoiseEntry]]:
        """
        Full pipeline: confidence filter -> pattern filter.
        Returns (clean_text, noise_log).
        """
        noise_log: List[NoiseEntry] = []

        if tokens:
            clean_tokens = []
            for tok, conf in tokens:
                if conf < confidence_threshold:
                    noise_log.append(NoiseEntry(tok, NoiseType.PHANTOM))
                else:
                    clean_tokens.append(tok)
            text = " ".join(clean_tokens)

        cleaned = self.filter_text(text)
        if cleaned != text:
            noise_log.append(NoiseEntry(text, NoiseType.MISREAD))

        return cleaned, noise_log
