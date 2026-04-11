"""
Cache lookup and multi-version detection for fingerprint-based processing.

Implements cache lookup logic for variant and base fingerprints,
diff-only processing, and multi-version detection.
"""
import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from ..models.block_v2 import Block
from ..models.metadata import RelationType
from ..storage.block_storage import BlockStorage


class CacheHitType(str, Enum):
    """Type of cache hit for processing decision."""
    FULL_HIT = "full_hit"  # variant_id found
    BASE_HIT = "base_hit"  # base_fp found, variant_id miss
    MISS = "miss"  # neither found


@dataclass
class CacheResult:
    """Result of a variant cache lookup."""
    hit_type: CacheHitType
    variant_id: str
    blocks: List[Block] = field(default_factory=list)
    base_fp: Optional[str] = None
    base_blocks: List[Block] = field(default_factory=list)


@dataclass
class BaseCacheResult:
    """Result of a base fingerprint cache lookup."""
    found: bool
    base_fp: str
    blocks: List[Block] = field(default_factory=list)
    variant_ids: List[str] = field(default_factory=list)


@dataclass
class VersionRelation:
    """Detected relationship between two versions."""
    source_variant: str
    target_variant: str
    relation_type: RelationType
    similarity_score: float
    details: Dict = field(default_factory=dict)


class CacheLookup:
    """
    Cache lookup for fingerprint-based block storage.
    
    Provides methods to check cache for existing translations
    and save new blocks for future lookups.
    """
    
    def __init__(self, storage_path: str):
        """
        Initialize cache lookup with storage path.
        
        Args:
            storage_path: Base path for block storage
        """
        self.storage = BlockStorage(storage_path)
        self.storage_path = Path(storage_path)
        self._index_file = self.storage_path / "cache_index.json"
        self._index = self._load_index()
    
    def _load_index(self) -> Dict:
        """Load cache index from disk."""
        if self._index_file.exists():
            with open(self._index_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"variants": {}, "bases": {}}
    
    def _save_index(self) -> None:
        """Save cache index to disk."""
        self._index_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._index_file, 'w', encoding='utf-8') as f:
            json.dump(self._index, f, ensure_ascii=False, indent=2)
    
    def lookup(self, variant_id: str) -> Optional[CacheResult]:
        """
        Check if variant exists in cache.
        
        Args:
            variant_id: The variant fingerprint to look up
            
        Returns:
            CacheResult if found, None otherwise
        """
        if variant_id in self._index["variants"]:
            entry = self._index["variants"][variant_id]
            base_fp = entry.get("base_fp")
            
            # Load variant blocks
            block_uids = entry.get("block_uids", [])
            blocks = []
            for uid in block_uids:
                try:
                    block = self.storage.load_block(uid)
                    blocks.append(block)
                except (FileNotFoundError, KeyError):
                    # Block file missing, skip
                    continue
            
            # Load base blocks if available
            base_blocks = []
            if base_fp and base_fp in self._index["bases"]:
                base_entry = self._index["bases"][base_fp]
                for uid in base_entry.get("block_uids", []):
                    try:
                        block = self.storage.load_block(uid)
                        base_blocks.append(block)
                    except (FileNotFoundError, KeyError):
                        continue
            
            return CacheResult(
                hit_type=CacheHitType.FULL_HIT,
                variant_id=variant_id,
                blocks=blocks,
                base_fp=base_fp,
                base_blocks=base_blocks
            )
        
        return None
    
    def lookup_base(self, base_fp: str) -> Optional[BaseCacheResult]:
        """
        Check if base fingerprint exists in cache.
        
        Args:
            base_fp: The base fingerprint to look up
            
        Returns:
            BaseCacheResult if found, None otherwise
        """
        if base_fp in self._index["bases"]:
            entry = self._index["bases"][base_fp]
            
            # Load base blocks
            block_uids = entry.get("block_uids", [])
            blocks = []
            for uid in block_uids:
                try:
                    block = self.storage.load_block(uid)
                    blocks.append(block)
                except (FileNotFoundError, KeyError):
                    continue
            
            return BaseCacheResult(
                found=True,
                base_fp=base_fp,
                blocks=blocks,
                variant_ids=entry.get("variant_ids", [])
            )
        
        return None
    
    def save_variant(self, variant_id: str, blocks: List[Block], base_fp: Optional[str] = None) -> None:
        """
        Save variant to cache.
        
        Args:
            variant_id: The variant fingerprint
            blocks: List of blocks to save
            base_fp: Optional base fingerprint linking
        """
        # Save all blocks
        block_uids = []
        for block in blocks:
            self.storage.save_block(block)
            block_uids.append(block.block_uid)
        
        # Update index
        self._index["variants"][variant_id] = {
            "block_uids": block_uids,
            "base_fp": base_fp
        }
        
        # Link to base if provided
        if base_fp:
            if base_fp not in self._index["bases"]:
                self._index["bases"][base_fp] = {
                    "block_uids": [],
                    "variant_ids": []
                }
            if variant_id not in self._index["bases"][base_fp]["variant_ids"]:
                self._index["bases"][base_fp]["variant_ids"].append(variant_id)
        
        self._save_index()
    
    def save_base(self, base_fp: str, blocks: List[Block]) -> None:
        """
        Save base blocks to cache.
        
        Args:
            base_fp: The base fingerprint
            blocks: List of base blocks to save
        """
        # Save all blocks
        block_uids = []
        for block in blocks:
            self.storage.save_block(block)
            block_uids.append(block.block_uid)
        
        # Update index
        if base_fp not in self._index["bases"]:
            self._index["bases"][base_fp] = {
                "block_uids": [],
                "variant_ids": []
            }
        
        self._index["bases"][base_fp]["block_uids"] = block_uids
        self._save_index()
    
    def determine_cache_strategy(self, base_fp: str, variant_id: str) -> Tuple[CacheHitType, Optional[CacheResult], Optional[BaseCacheResult]]:
        """
        Determine the cache strategy for processing.
        
        Args:
            base_fp: The base fingerprint
            variant_id: The variant fingerprint
            
        Returns:
            Tuple of (hit_type, variant_result, base_result)
        """
        # Check variant first
        variant_result = self.lookup(variant_id)
        if variant_result:
            return CacheHitType.FULL_HIT, variant_result, None
        
        # Check base
        base_result = self.lookup_base(base_fp)
        if base_result:
            return CacheHitType.BASE_HIT, None, base_result
        
        return CacheHitType.MISS, None, None


class MultiVersionDetector:
    """
    Detect relationships between different versions of the same comic.
    
    Identifies:
    - same_art_diff_censor: High pixel similarity + censor_signature diff
    - same_script_diff_edit: Text diff + structural similarity
    """
    
    # Thresholds for similarity detection
    PIXEL_SIMILARITY_THRESHOLD = 0.95
    STRUCTURAL_SIMILARITY_THRESHOLD = 0.85
    TEXT_SIMILARITY_THRESHOLD = 0.80
    
    @staticmethod
    def compute_pixel_similarity(blocks_a: List[Block], blocks_b: List[Block]) -> float:
        """
        Compute pixel similarity between two sets of blocks.
        
        Uses bounding box overlap as a proxy for visual similarity.
        
        Args:
            blocks_a: First set of blocks
            blocks_b: Second set of blocks
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        if not blocks_a or not blocks_b:
            return 0.0
        
        # Compute average IoU across matched blocks
        total_iou = 0.0
        matched_count = 0
        
        for block_a in blocks_a:
            best_iou = 0.0
            for block_b in blocks_b:
                iou = MultiVersionDetector._compute_bbox_iou(block_a.bbox, block_b.bbox)
                best_iou = max(best_iou, iou)
            total_iou += best_iou
            matched_count += 1
        
        return total_iou / matched_count if matched_count > 0 else 0.0
    
    @staticmethod
    def _compute_bbox_iou(bbox_a: List[int], bbox_b: List[int]) -> float:
        """
        Compute Intersection over Union for two bounding boxes.
        
        Args:
            bbox_a: First bbox [x1, y1, x2, y2]
            bbox_b: Second bbox [x1, y1, x2, y2]
            
        Returns:
            IoU score between 0.0 and 1.0
        """
        # Compute intersection
        x1 = max(bbox_a[0], bbox_b[0])
        y1 = max(bbox_a[1], bbox_b[1])
        x2 = min(bbox_a[2], bbox_b[2])
        y2 = min(bbox_a[3], bbox_b[3])
        
        if x2 <= x1 or y2 <= y1:
            return 0.0
        
        intersection = (x2 - x1) * (y2 - y1)
        
        # Compute areas
        area_a = (bbox_a[2] - bbox_a[0]) * (bbox_a[3] - bbox_a[1])
        area_b = (bbox_b[2] - bbox_b[0]) * (bbox_b[3] - bbox_b[1])
        
        # Compute union
        union = area_a + area_b - intersection
        
        return intersection / union if union > 0 else 0.0
    
    @staticmethod
    def compute_text_similarity(blocks_a: List[Block], blocks_b: List[Block]) -> float:
        """
        Compute text similarity between two sets of blocks.
        
        Uses character-level similarity of original texts.
        
        Args:
            blocks_a: First set of blocks
            blocks_b: Second set of blocks
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        if not blocks_a or not blocks_b:
            return 0.0
        
        # Extract all text from blocks
        def extract_texts(blocks: List[Block]) -> str:
            texts = []
            for block in blocks:
                for ot in block.original_texts:
                    texts.append(ot.text)
            return " ".join(texts)
        
        text_a = extract_texts(blocks_a)
        text_b = extract_texts(blocks_b)
        
        if not text_a or not text_b:
            return 0.0
        
        # Simple character-level similarity (Jaccard index on character n-grams)
        def get_char_ngrams(text: str, n: int = 3) -> set:
            return set(text[i:i+n] for i in range(len(text) - n + 1))
        
        ngrams_a = get_char_ngrams(text_a)
        ngrams_b = get_char_ngrams(text_b)
        
        if not ngrams_a or not ngrams_b:
            return 0.0
        
        intersection = len(ngrams_a & ngrams_b)
        union = len(ngrams_a | ngrams_b)
        
        return intersection / union if union > 0 else 0.0
    
    @staticmethod
    def compute_structural_similarity(blocks_a: List[Block], blocks_b: List[Block]) -> float:
        """
        Compute structural similarity between two sets of blocks.
        
        Considers block types, counts, and spatial distribution.
        
        Args:
            blocks_a: First set of blocks
            blocks_b: Second set of blocks
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        if not blocks_a or not blocks_b:
            return 0.0
        
        # Compare block type distributions
        def get_type_distribution(blocks: List[Block]) -> Dict[str, float]:
            type_counts = {}
            for block in blocks:
                type_name = block.type.value
                type_counts[type_name] = type_counts.get(type_name, 0) + 1
            total = len(blocks)
            return {k: v / total for k, v in type_counts.items()}
        
        dist_a = get_type_distribution(blocks_a)
        dist_b = get_type_distribution(blocks_b)
        
        # Compute similarity between distributions
        all_types = set(dist_a.keys()) | set(dist_b.keys())
        if not all_types:
            return 0.0
        
        diff_sum = 0.0
        for t in all_types:
            diff_sum += abs(dist_a.get(t, 0) - dist_b.get(t, 0))
        
        type_similarity = 1.0 - (diff_sum / 2.0)
        
        # Compare block count similarity
        count_similarity = min(len(blocks_a), len(blocks_b)) / max(len(blocks_a), len(blocks_b))
        
        # Weighted combination
        return 0.6 * type_similarity + 0.4 * count_similarity
    
    @classmethod
    def detect_relation(
        cls,
        blocks_a: List[Block],
        blocks_b: List[Block],
        censor_sig_a: str,
        censor_sig_b: str
    ) -> Optional[VersionRelation]:
        """
        Detect the relationship between two versions.
        
        Args:
            blocks_a: Blocks from first version
            blocks_b: Blocks from second version
            censor_sig_a: Censor signature of first version
            censor_sig_b: Censor signature of second version
            
        Returns:
            VersionRelation if a relationship is detected, None otherwise
        """
        pixel_sim = cls.compute_pixel_similarity(blocks_a, blocks_b)
        text_sim = cls.compute_text_similarity(blocks_a, blocks_b)
        struct_sim = cls.compute_structural_similarity(blocks_a, blocks_b)
        
        # Check for same_art_diff_censor
        # High pixel similarity + different censor signatures
        censor_diff = censor_sig_a != censor_sig_b
        if pixel_sim >= cls.PIXEL_SIMILARITY_THRESHOLD and censor_diff:
            return VersionRelation(
                source_variant="",  # To be filled by caller
                target_variant="",  # To be filled by caller
                relation_type=RelationType.SAME_ART_DIFF_CENSOR,
                similarity_score=pixel_sim,
                details={
                    "pixel_similarity": pixel_sim,
                    "censor_diff": True,
                    "censor_sig_a": censor_sig_a,
                    "censor_sig_b": censor_sig_b
                }
            )
        
        # Check for same_script_diff_edit
        # Text diff + structural similarity
        text_diff = text_sim < cls.TEXT_SIMILARITY_THRESHOLD
        if struct_sim >= cls.STRUCTURAL_SIMILARITY_THRESHOLD and text_diff:
            return VersionRelation(
                source_variant="",  # To be filled by caller
                target_variant="",  # To be filled by caller
                relation_type=RelationType.SAME_SCRIPT_DIFF_EDIT,
                similarity_score=struct_sim,
                details={
                    "structural_similarity": struct_sim,
                    "text_similarity": text_sim,
                    "text_diff": True
                }
            )
        
        return None
