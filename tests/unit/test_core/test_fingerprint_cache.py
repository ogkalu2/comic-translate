"""
Unit tests for fingerprint cache lookup and multi-version detection.
"""
import pytest
from pathlib import Path

from comic_translate_core.fingerprint.cache import (
    CacheLookup,
    CacheHitType,
    CacheResult,
    BaseCacheResult,
    MultiVersionDetector,
    VersionRelation
)
from comic_translate_core.models.block_v2 import (
    Block,
    BlockType,
    OriginalText,
    TranslationVersion,
    TranslationHistory
)
from comic_translate_core.models.metadata import RelationType


@pytest.fixture
def storage_path(tmp_path):
    """Create a temporary storage path for tests."""
    return str(tmp_path / "cache_storage")


@pytest.fixture
def sample_block():
    """Create a sample block for testing."""
    return Block(
        block_uid="base_abc123:1:0:0",
        nsfw_flag=False,
        type=BlockType.DIALOGUE,
        bbox=[100, 200, 300, 400],
        original_texts=[OriginalText("variant_001", "ja", "テストテキスト")],
        translations={
            "en": {
                "v1": TranslationVersion(
                    text="Test text",
                    status="approved",
                    weight=1.0,
                    history=[TranslationHistory("translate", "gpt-4")],
                    source="gpt-4"
                )
            }
        },
        semantic_routing=None,
        embedding=None
    )


@pytest.fixture
def sample_blocks():
    """Create multiple sample blocks for testing."""
    return [
        Block(
            block_uid="base_abc123:1:0:0",
            nsfw_flag=False,
            type=BlockType.DIALOGUE,
            bbox=[100, 100, 200, 200],
            original_texts=[OriginalText("variant_001", "ja", "こんにちは")],
            translations={},
            semantic_routing=None,
            embedding=None
        ),
        Block(
            block_uid="base_abc123:1:1:0",
            nsfw_flag=False,
            type=BlockType.NARRATION,
            bbox=[300, 300, 400, 400],
            original_texts=[OriginalText("variant_001", "ja", "ナレーション")],
            translations={},
            semantic_routing=None,
            embedding=None
        ),
        Block(
            block_uid="base_abc123:1:2:0",
            nsfw_flag=False,
            type=BlockType.SFX,
            bbox=[500, 500, 600, 600],
            original_texts=[OriginalText("variant_001", "ja", "ドン")],
            translations={},
            semantic_routing=None,
            embedding=None
        )
    ]


class TestCacheLookup:
    """Tests for CacheLookup class."""
    
    def test_init_creates_storage(self, storage_path):
        """Test that initialization creates storage directory."""
        cache = CacheLookup(storage_path)
        assert Path(storage_path).exists()
    
    def test_save_and_lookup_variant(self, storage_path, sample_block):
        """Test saving and looking up a variant."""
        cache = CacheLookup(storage_path)
        
        # Save variant
        cache.save_variant("variant_001", [sample_block], base_fp="base_abc123")
        
        # Lookup variant
        result = cache.lookup("variant_001")
        
        assert result is not None
        assert result.hit_type == CacheHitType.FULL_HIT
        assert result.variant_id == "variant_001"
        assert result.base_fp == "base_abc123"
        assert len(result.blocks) == 1
        assert result.blocks[0].block_uid == sample_block.block_uid
    
    def test_lookup_nonexistent_variant(self, storage_path):
        """Test looking up a variant that doesn't exist."""
        cache = CacheLookup(storage_path)
        
        result = cache.lookup("nonexistent_variant")
        
        assert result is None
    
    def test_save_and_lookup_base(self, storage_path, sample_blocks):
        """Test saving and looking up a base fingerprint."""
        cache = CacheLookup(storage_path)
        
        # Save base
        cache.save_base("base_abc123", sample_blocks)
        
        # Lookup base
        result = cache.lookup_base("base_abc123")
        
        assert result is not None
        assert result.found is True
        assert result.base_fp == "base_abc123"
        assert len(result.blocks) == 3
    
    def test_lookup_nonexistent_base(self, storage_path):
        """Test looking up a base that doesn't exist."""
        cache = CacheLookup(storage_path)
        
        result = cache.lookup_base("nonexistent_base")
        
        assert result is None
    
    def test_save_variant_links_to_base(self, storage_path, sample_block):
        """Test that saving a variant links it to the base."""
        cache = CacheLookup(storage_path)
        
        # Save base first
        cache.save_base("base_abc123", [sample_block])
        
        # Save variant linked to base
        cache.save_variant("variant_001", [sample_block], base_fp="base_abc123")
        
        # Check base has variant linked
        base_result = cache.lookup_base("base_abc123")
        assert "variant_001" in base_result.variant_ids
    
    def test_save_multiple_variants_same_base(self, storage_path, sample_block):
        """Test saving multiple variants linked to the same base."""
        cache = CacheLookup(storage_path)
        
        # Save base
        cache.save_base("base_abc123", [sample_block])
        
        # Save multiple variants
        cache.save_variant("variant_001", [sample_block], base_fp="base_abc123")
        cache.save_variant("variant_002", [sample_block], base_fp="base_abc123")
        
        # Check base has both variants linked
        base_result = cache.lookup_base("base_abc123")
        assert "variant_001" in base_result.variant_ids
        assert "variant_002" in base_result.variant_ids
    
    def test_determine_cache_strategy_full_hit(self, storage_path, sample_block):
        """Test cache strategy when variant is found."""
        cache = CacheLookup(storage_path)
        
        # Save variant
        cache.save_variant("variant_001", [sample_block], base_fp="base_abc123")
        
        # Determine strategy
        hit_type, variant_result, base_result = cache.determine_cache_strategy(
            "base_abc123", "variant_001"
        )
        
        assert hit_type == CacheHitType.FULL_HIT
        assert variant_result is not None
        assert variant_result.variant_id == "variant_001"
        assert base_result is None
    
    def test_determine_cache_strategy_base_hit(self, storage_path, sample_block):
        """Test cache strategy when only base is found."""
        cache = CacheLookup(storage_path)
        
        # Save base only
        cache.save_base("base_abc123", [sample_block])
        
        # Determine strategy
        hit_type, variant_result, base_result = cache.determine_cache_strategy(
            "base_abc123", "variant_001"
        )
        
        assert hit_type == CacheHitType.BASE_HIT
        assert variant_result is None
        assert base_result is not None
        assert base_result.base_fp == "base_abc123"
    
    def test_determine_cache_strategy_miss(self, storage_path):
        """Test cache strategy when neither variant nor base is found."""
        cache = CacheLookup(storage_path)
        
        # Determine strategy with no data
        hit_type, variant_result, base_result = cache.determine_cache_strategy(
            "base_abc123", "variant_001"
        )
        
        assert hit_type == CacheHitType.MISS
        assert variant_result is None
        assert base_result is None
    
    def test_persistence_across_instances(self, storage_path, sample_block):
        """Test that cache data persists across CacheLookup instances."""
        # First instance saves data
        cache1 = CacheLookup(storage_path)
        cache1.save_variant("variant_001", [sample_block], base_fp="base_abc123")
        
        # Second instance should see the data
        cache2 = CacheLookup(storage_path)
        result = cache2.lookup("variant_001")
        
        assert result is not None
        assert result.variant_id == "variant_001"


class TestMultiVersionDetector:
    """Tests for MultiVersionDetector class."""
    
    def test_compute_bbox_iou_no_overlap(self):
        """Test IoU computation with non-overlapping boxes."""
        bbox_a = [0, 0, 100, 100]
        bbox_b = [200, 200, 300, 300]
        
        iou = MultiVersionDetector._compute_bbox_iou(bbox_a, bbox_b)
        
        assert iou == 0.0
    
    def test_compute_bbox_iou_identical(self):
        """Test IoU computation with identical boxes."""
        bbox = [100, 100, 200, 200]
        
        iou = MultiVersionDetector._compute_bbox_iou(bbox, bbox)
        
        assert iou == 1.0
    
    def test_compute_bbox_iou_partial_overlap(self):
        """Test IoU computation with partial overlap."""
        bbox_a = [0, 0, 100, 100]
        bbox_b = [50, 50, 150, 150]
        
        iou = MultiVersionDetector._compute_bbox_iou(bbox_a, bbox_b)
        
        # Intersection: 50x50 = 2500
        # Union: 10000 + 10000 - 2500 = 17500
        # IoU = 2500 / 17500 ≈ 0.143
        assert 0.14 < iou < 0.15
    
    def test_compute_pixel_similarity_empty_blocks(self):
        """Test pixel similarity with empty block lists."""
        similarity = MultiVersionDetector.compute_pixel_similarity([], [])
        assert similarity == 0.0
    
    def test_compute_pixel_similarity_identical_blocks(self, sample_blocks):
        """Test pixel similarity with identical blocks."""
        similarity = MultiVersionDetector.compute_pixel_similarity(sample_blocks, sample_blocks)
        assert similarity == 1.0
    
    def test_compute_pixel_similarity_different_blocks(self):
        """Test pixel similarity with completely different blocks."""
        blocks_a = [
            Block("a:0:0:0", False, BlockType.DIALOGUE, [0, 0, 100, 100], [], {}, None, None)
        ]
        blocks_b = [
            Block("b:0:0:0", False, BlockType.DIALOGUE, [500, 500, 600, 600], [], {}, None, None)
        ]
        
        similarity = MultiVersionDetector.compute_pixel_similarity(blocks_a, blocks_b)
        assert similarity == 0.0
    
    def test_compute_text_similarity_empty_blocks(self):
        """Test text similarity with empty block lists."""
        similarity = MultiVersionDetector.compute_text_similarity([], [])
        assert similarity == 0.0
    
    def test_compute_text_similarity_identical_text(self):
        """Test text similarity with identical text."""
        blocks_a = [
            Block("a:0:0:0", False, BlockType.DIALOGUE, [0, 0, 100, 100],
                  [OriginalText("v1", "ja", "こんにちは世界")], {}, None, None)
        ]
        blocks_b = [
            Block("b:0:0:0", False, BlockType.DIALOGUE, [0, 0, 100, 100],
                  [OriginalText("v2", "ja", "こんにちは世界")], {}, None, None)
        ]
        
        similarity = MultiVersionDetector.compute_text_similarity(blocks_a, blocks_b)
        assert similarity == 1.0
    
    def test_compute_text_similarity_different_text(self):
        """Test text similarity with different text."""
        blocks_a = [
            Block("a:0:0:0", False, BlockType.DIALOGUE, [0, 0, 100, 100],
                  [OriginalText("v1", "ja", "こんにちは")], {}, None, None)
        ]
        blocks_b = [
            Block("b:0:0:0", False, BlockType.DIALOGUE, [0, 0, 100, 100],
                  [OriginalText("v2", "ja", "さようなら")], {}, None, None)
        ]
        
        similarity = MultiVersionDetector.compute_text_similarity(blocks_a, blocks_b)
        assert similarity < 0.5
    
    def test_compute_structural_similarity_empty_blocks(self):
        """Test structural similarity with empty block lists."""
        similarity = MultiVersionDetector.compute_structural_similarity([], [])
        assert similarity == 0.0
    
    def test_compute_structural_similarity_identical_structure(self, sample_blocks):
        """Test structural similarity with identical structure."""
        similarity = MultiVersionDetector.compute_structural_similarity(sample_blocks, sample_blocks)
        assert similarity == 1.0
    
    def test_compute_structural_similarity_different_types(self):
        """Test structural similarity with different block types."""
        blocks_a = [
            Block("a:0:0:0", False, BlockType.DIALOGUE, [0, 0, 100, 100], [], {}, None, None),
            Block("a:0:1:0", False, BlockType.DIALOGUE, [0, 0, 100, 100], [], {}, None, None)
        ]
        blocks_b = [
            Block("b:0:0:0", False, BlockType.SFX, [0, 0, 100, 100], [], {}, None, None),
            Block("b:0:1:0", False, BlockType.SFX, [0, 0, 100, 100], [], {}, None, None)
        ]
        
        similarity = MultiVersionDetector.compute_structural_similarity(blocks_a, blocks_b)
        # Same count but different types
        assert similarity < 1.0
    
    def test_detect_relation_same_art_diff_censor(self):
        """Test detection of same_art_diff_censor relationship."""
        # Create blocks with identical positions (high pixel similarity)
        blocks_a = [
            Block("a:0:0:0", False, BlockType.DIALOGUE, [100, 100, 200, 200],
                  [OriginalText("v1", "ja", "テスト")], {}, None, None)
        ]
        blocks_b = [
            Block("b:0:0:0", False, BlockType.DIALOGUE, [100, 100, 200, 200],
                  [OriginalText("v2", "ja", "テスト")], {}, None, None)
        ]
        
        relation = MultiVersionDetector.detect_relation(
            blocks_a, blocks_b,
            censor_sig_a="none",
            censor_sig_b="censored"
        )
        
        assert relation is not None
        assert relation.relation_type == RelationType.SAME_ART_DIFF_CENSOR
        assert relation.details["censor_diff"] is True
    
    def test_detect_relation_same_script_diff_edit(self):
        """Test detection of same_script_diff_edit relationship."""
        # Create blocks with similar structure but different text
        blocks_a = [
            Block("a:0:0:0", False, BlockType.DIALOGUE, [100, 100, 200, 200],
                  [OriginalText("v1", "ja", "こんにちは世界")], {}, None, None),
            Block("a:0:1:0", False, BlockType.NARRATION, [300, 300, 400, 400],
                  [OriginalText("v1", "ja", "ナレーション")], {}, None, None)
        ]
        blocks_b = [
            Block("b:0:0:0", False, BlockType.DIALOGUE, [110, 110, 210, 210],
                  [OriginalText("v2", "ja", "さようなら世界")], {}, None, None),
            Block("b:0:1:0", False, BlockType.NARRATION, [310, 310, 410, 410],
                  [OriginalText("v2", "ja", "別のナレーション")], {}, None, None)
        ]
        
        relation = MultiVersionDetector.detect_relation(
            blocks_a, blocks_b,
            censor_sig_a="none",
            censor_sig_b="none"
        )
        
        assert relation is not None
        assert relation.relation_type == RelationType.SAME_SCRIPT_DIFF_EDIT
        assert relation.details["text_diff"] is True
    
    def test_detect_relation_no_relation(self):
        """Test when no relationship is detected."""
        # Create blocks with low similarity
        blocks_a = [
            Block("a:0:0:0", False, BlockType.DIALOGUE, [0, 0, 100, 100],
                  [OriginalText("v1", "ja", "こんにちは")], {}, None, None)
        ]
        blocks_b = [
            Block("b:0:0:0", False, BlockType.SFX, [500, 500, 600, 600],
                  [OriginalText("v2", "ja", "ドン")], {}, None, None)
        ]
        
        relation = MultiVersionDetector.detect_relation(
            blocks_a, blocks_b,
            censor_sig_a="none",
            censor_sig_b="none"
        )
        
        assert relation is None
    
    def test_detect_relation_empty_blocks(self):
        """Test detection with empty block lists."""
        relation = MultiVersionDetector.detect_relation(
            [], [],
            censor_sig_a="none",
            censor_sig_b="none"
        )
        
        assert relation is None


class TestCacheResultTypes:
    """Tests for cache result dataclasses."""
    
    def test_cache_result_defaults(self):
        """Test CacheResult default values."""
        result = CacheResult(
            hit_type=CacheHitType.MISS,
            variant_id="test_variant"
        )
        
        assert result.hit_type == CacheHitType.MISS
        assert result.variant_id == "test_variant"
        assert result.blocks == []
        assert result.base_fp is None
        assert result.base_blocks == []
    
    def test_base_cache_result_defaults(self):
        """Test BaseCacheResult default values."""
        result = BaseCacheResult(
            found=False,
            base_fp="test_base"
        )
        
        assert result.found is False
        assert result.base_fp == "test_base"
        assert result.blocks == []
        assert result.variant_ids == []
    
    def test_version_relation_defaults(self):
        """Test VersionRelation default values."""
        relation = VersionRelation(
            source_variant="v1",
            target_variant="v2",
            relation_type=RelationType.SAME_ART_DIFF_CENSOR,
            similarity_score=0.95
        )
        
        assert relation.source_variant == "v1"
        assert relation.target_variant == "v2"
        assert relation.relation_type == RelationType.SAME_ART_DIFF_CENSOR
        assert relation.similarity_score == 0.95
        assert relation.details == {}
