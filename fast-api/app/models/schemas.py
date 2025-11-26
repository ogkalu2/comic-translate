"""
Pydantic models for API request/response schemas.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class TextBlockSchema(BaseModel):
    """Schema for a text block."""
    bbox: List[float] = Field(..., description="Bounding box coordinates [x1, y1, x2, y2]")
    text: str = Field(default="", description="OCR extracted text")
    translation: str = Field(default="", description="Translated text")
    text_class: str = Field(default="", description="Text classification (e.g., text_free, text_bubble)")
    angle: float = Field(default=0, description="Text block rotation angle")
    source_lang: str = Field(default="", description="Source language code")
    target_lang: str = Field(default="", description="Target language code")
    bubble_bbox: Optional[List[float]] = Field(default=None, description="Speech bubble bounding box")
    inpaint_bboxes: Optional[List[List[float]]] = Field(default=None, description="Inpainting region bounding boxes")


class DetectionResponse(BaseModel):
    """Response schema for text detection."""
    blocks: List[TextBlockSchema] = Field(..., description="List of detected text blocks")
    count: int = Field(..., description="Number of detected blocks")
    image_shape: List[int] = Field(..., description="Image dimensions [height, width, channels]")


class OCRResponse(BaseModel):
    """Response schema for OCR."""
    blocks: List[TextBlockSchema] = Field(..., description="List of text blocks with OCR results")
    count: int = Field(..., description="Number of processed blocks")
    source_lang: str = Field(..., description="Source language used for OCR")


class TranslationResponse(BaseModel):
    """Response schema for translation."""
    blocks: List[TextBlockSchema] = Field(..., description="List of text blocks with translations")
    count: int = Field(..., description="Number of translated blocks")
    source_lang: str = Field(..., description="Source language")
    target_lang: str = Field(..., description="Target language")


class InpaintingResponse(BaseModel):
    """Response schema for inpainting."""
    inpainted_image: str = Field(..., description="Base64 encoded inpainted image")
    blocks_count: int = Field(..., description="Number of blocks inpainted")
    image_shape: List[int] = Field(..., description="Image dimensions [height, width, channels]")


class FullPipelineResponse(BaseModel):
    """Response schema for full translation pipeline."""
    blocks: List[TextBlockSchema] = Field(..., description="List of processed text blocks")
    count: int = Field(..., description="Number of processed blocks")
    source_lang: str = Field(..., description="Source language")
    target_lang: str = Field(..., description="Target language")
    pipeline_steps: List[str] = Field(..., description="List of pipeline steps executed")
    inpainted_image: Optional[str] = Field(default=None, description="Base64 encoded inpainted image (if requested)")


class ErrorResponse(BaseModel):
    """Error response schema."""
    detail: str = Field(..., description="Error message")
    error: Optional[str] = Field(default=None, description="Detailed error information")
