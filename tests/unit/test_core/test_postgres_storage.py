"""Unit tests for PostgreSQL storage backend.

These tests use an in-memory SQLite database for testing ORM logic
without requiring a running PostgreSQL instance.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

# Skip all tests if postgres dependencies are not installed
pytest.importorskip("sqlalchemy", reason="sqlalchemy not installed")
pytest.importorskip("pgvector", reason="pgvector not installed")

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from comic_translate_core.storage.postgres import (
    Base,
    ComicModel,
    BlockModel,
    ContributionModel,
    PostgresStorage,
    create_engine,
    create_session_factory,
)
from comic_translate_core.storage.vector import VectorStorage
from comic_translate_core.models import (
    ScriptExport,
    ScriptBlock,
    BlockType,
    BlockContext,
    QAPatchSet,
    QAPatch,
    PatchCategory,
)
from comic_translate_core.models.block_v2 import (
    Block,
    BlockType as BlockTypeV2,
    OriginalText,
    TranslationVersion,
    TranslationHistory,
    SemanticRouting,
)


@pytest_asyncio.fixture
async def engine():
    """Create an in-memory SQLite engine for testing."""
    # Use SQLite for unit tests (pgvector not available in SQLite)
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    """Create a session factory for testing."""
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def storage(session_factory):
    """Create a PostgresStorage instance for testing."""
    return PostgresStorage(session_factory)


@pytest_asyncio.fixture
async def vector_storage(session_factory):
    """Create a VectorStorage instance for testing."""
    return VectorStorage(session_factory)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def make_script_export() -> ScriptExport:
    """Create a sample ScriptExport for testing."""
    return ScriptExport(
        version="2.0",
        comic_id="test_comic",
        base_fp="test_comic",
        script_id="test_script",
        source_lang="ja",
        target_lang="en",
        exported_at=1700000000.0,
        page_range=[1, 10],
        active_variant="default",
        variants={},
        glossary_snapshot={},
        blocks=[
            ScriptBlock(
                block_id="0",
                page=1,
                type=BlockType.DIALOGUE,
                bbox=[100, 200, 300, 400],
                original="こんにちは",
                translated="Hello",
                original_variant="default",
                context=BlockContext(speaker="Alice"),
                qa_metadata=None,
            ),
            ScriptBlock(
                block_id="1",
                page=1,
                type=BlockType.NARRATION,
                bbox=[50, 50, 200, 100],
                original="物語の始まり",
                translated="The beginning of the story",
                original_variant="default",
                context=BlockContext(),
                qa_metadata=None,
            ),
        ],
    )


def make_patch_set() -> QAPatchSet:
    """Create a sample QAPatchSet for testing."""
    return QAPatchSet(
        version="1.0",
        comic_id="test_comic",
        base_fp="test_comic",
        created_at=1700000000.0,
        qa_model="gpt-4",
        chunk_range={"start": "0", "end": "10"},
        summary={"total_patches": 1},
        patches=[
            QAPatch(
                block_id="0",
                original="こんにちは",
                old_translated="Hello",
                new_translated="Hi there",
                reason="More natural greeting",
                category=PatchCategory.TONE,
                confidence=0.95,
            ),
        ],
    )


def make_block() -> Block:
    """Create a sample Block v2 for testing."""
    return Block(
        block_uid="test_comic:1:0:0",
        nsfw_flag=False,
        type=BlockTypeV2.DIALOGUE,
        bbox=[100, 200, 300, 400],
        original_texts=[
            OriginalText(variant_id="pixiv", lang="ja", text="こんにちは")
        ],
        translations={
            "en": {
                "v1": TranslationVersion(
                    text="Hello",
                    status="approved",
                    weight=1.0,
                    history=[
                        TranslationHistory(
                            action="translate",
                            source="gpt-4",
                            timestamp=1700000000.0,
                        )
                    ],
                    source="gpt-4",
                )
            }
        },
        semantic_routing=SemanticRouting(
            ner_entities=[{"name": "Alice", "type": "PERSON"}],
            sfx_detected=False,
            route="standard",
        ),
        embedding=[0.1] * 384,
    )


# ---------------------------------------------------------------------------
# PostgresStorage Tests
# ---------------------------------------------------------------------------

class TestPostgresStorage:
    """Tests for PostgresStorage class."""

    @pytest.mark.asyncio
    async def test_save_and_load_script(self, storage, session_factory):
        """Test saving and loading a ScriptExport."""
        script = make_script_export()

        # Save script using async method directly
        await storage._save_script_async(script, "test_comic")

        # Load script
        loaded = await storage._load_script_async("test_comic")

        assert loaded.base_fp == "test_comic"
        assert loaded.comic_id == "test_comic"
        assert len(loaded.blocks) == 2
        assert loaded.blocks[0].original == "こんにちは"
        assert loaded.blocks[0].translated == "Hello"
        assert loaded.blocks[0].type == BlockType.DIALOGUE
        assert loaded.blocks[1].type == BlockType.NARRATION

    @pytest.mark.asyncio
    async def test_save_script_increments_hit_count(self, storage, session_factory):
        """Test that saving a script increments the hit count."""
        script = make_script_export()

        await storage._save_script_async(script, "test_comic")
        await storage._save_script_async(script, "test_comic")

        async with session_factory() as session:
            comic = await session.get(ComicModel, "test_comic")
            assert comic.hit_count == 2

    @pytest.mark.asyncio
    async def test_load_nonexistent_script(self, storage):
        """Test loading a script that doesn't exist raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            await storage._load_script_async("nonexistent")

    @pytest.mark.asyncio
    async def test_save_and_load_patch(self, storage, session_factory):
        """Test saving and loading a QAPatchSet."""
        # First save a script to ensure comic exists
        script = make_script_export()
        await storage._save_script_async(script, "test_comic")

        patch_set = make_patch_set()
        await storage._save_patch_async(patch_set, "test_comic")

        loaded = await storage._load_patch_async("test_comic")

        assert len(loaded.patches) == 1
        assert loaded.patches[0].block_id == "0"
        assert loaded.patches[0].original == "こんにちは"
        assert loaded.patches[0].old_translated == "Hello"
        assert loaded.patches[0].new_translated == "Hi there"
        assert loaded.patches[0].category == PatchCategory.TONE
        assert loaded.patches[0].confidence == 0.95

    @pytest.mark.asyncio
    async def test_save_and_load_block(self, storage, session_factory):
        """Test saving and loading a Block v2."""
        block = make_block()

        await storage.save_block_async(block)
        loaded = await storage.load_block_async("test_comic:1:0:0")

        assert loaded.block_uid == "test_comic:1:0:0"
        assert loaded.type == BlockTypeV2.DIALOGUE
        assert loaded.nsfw_flag is False
        assert len(loaded.original_texts) == 1
        assert loaded.original_texts[0].text == "こんにちは"
        assert loaded.translations["en"]["v1"].text == "Hello"
        assert loaded.translations["en"]["v1"].status == "approved"
        assert loaded.semantic_routing.route == "standard"

    @pytest.mark.asyncio
    async def test_list_blocks(self, storage, session_factory):
        """Test listing blocks for a comic."""
        block1 = Block(
            block_uid="test_comic:1:0:0",
            nsfw_flag=False,
            type=BlockTypeV2.DIALOGUE,
            bbox=[0, 0, 10, 10],
            original_texts=[],
            translations={},
            semantic_routing=None,
            embedding=None,
        )
        block2 = Block(
            block_uid="test_comic:1:1:0",
            nsfw_flag=False,
            type=BlockTypeV2.NARRATION,
            bbox=[0, 0, 10, 10],
            original_texts=[],
            translations={},
            semantic_routing=None,
            embedding=None,
        )

        await storage.save_block_async(block1)
        await storage.save_block_async(block2)

        block_uids = await storage.list_blocks_async("test_comic")
        assert len(block_uids) == 2
        assert "test_comic:1:0:0" in block_uids
        assert "test_comic:1:1:0" in block_uids

    @pytest.mark.asyncio
    async def test_update_block(self, storage, session_factory):
        """Test updating an existing block."""
        block = make_block()
        await storage.save_block_async(block)

        # Update the block
        block.translations["en"]["v1"].text = "Updated translation"
        await storage.save_block_async(block)

        loaded = await storage.load_block_async("test_comic:1:0:0")
        assert loaded.translations["en"]["v1"].text == "Updated translation"

    @pytest.mark.asyncio
    async def test_load_nonexistent_block(self, storage):
        """Test loading a block that doesn't exist raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            await storage.load_block_async("nonexistent:0:0:0")


# ---------------------------------------------------------------------------
# VectorStorage Tests
# ---------------------------------------------------------------------------

class TestVectorStorage:
    """Tests for VectorStorage class."""

    @pytest.mark.asyncio
    async def test_store_and_get_embedding(self, vector_storage, session_factory):
        """Test storing and retrieving an embedding."""
        # First create a comic and block
        async with session_factory() as session:
            async with session.begin():
                session.add(ComicModel(base_fp="test_comic"))
                session.add(
                    BlockModel(
                        block_uid="test_comic:1:0:0",
                        base_fp="test_comic",
                        block_type="dialogue",
                        bbox=[0, 0, 10, 10],
                        original_texts=[],
                        translations={},
                        nsfw_flag=False,
                    )
                )

        embedding = [0.1] * 384
        await vector_storage.store_embedding("test_comic:1:0:0", embedding)

        retrieved = await vector_storage.get_embedding("test_comic:1:0:0")
        assert retrieved is not None
        assert len(retrieved) == 384

    @pytest.mark.asyncio
    async def test_get_nonexistent_embedding(self, vector_storage):
        """Test getting embedding for nonexistent block returns None."""
        result = await vector_storage.get_embedding("nonexistent:0:0:0")
        assert result is None

    @pytest.mark.asyncio
    async def test_store_embedding_nonexistent_block(self, vector_storage):
        """Test storing embedding for nonexistent block raises error."""
        with pytest.raises(FileNotFoundError):
            await vector_storage.store_embedding("nonexistent:0:0:0", [0.1] * 384)

    @pytest.mark.asyncio
    async def test_store_comic_embedding(self, vector_storage, session_factory):
        """Test storing a comic meta embedding."""
        async with session_factory() as session:
            async with session.begin():
                session.add(ComicModel(base_fp="test_comic"))

        embedding = [0.2] * 384
        await vector_storage.store_comic_embedding("test_comic", embedding)

        async with session_factory() as session:
            comic = await session.get(ComicModel, "test_comic")
            assert comic.meta_embedding is not None

    @pytest.mark.asyncio
    async def test_search_similar_blocks_uses_named_bind_params(self):
        """Vector search should use SQLAlchemy-compatible named parameters."""
        result = MagicMock()
        result.fetchall.return_value = [("test_comic:1:0:0", 0.98)]

        session = AsyncMock()
        session.execute.return_value = result

        class _SessionFactory:
            def __call__(self):
                return self

            async def __aenter__(self):
                return session

            async def __aexit__(self, exc_type, exc, tb):
                return False

        storage = VectorStorage(_SessionFactory())
        rows = await storage.search_similar_blocks([0.1, 0.2], limit=5, base_fp="test_comic")

        assert rows == [("test_comic:1:0:0", 0.98)]
        query = str(session.execute.await_args.args[0])
        params = session.execute.await_args.args[1]
        assert ":embedding" in query
        assert ":base_fp" in query
        assert ":limit" in query
        assert params == {
            "embedding": "[0.1,0.2]",
            "base_fp": "test_comic",
            "limit": 5,
        }

    @pytest.mark.asyncio
    async def test_search_similar_comics_uses_named_bind_params(self):
        """Comic similarity search should use SQLAlchemy-compatible named parameters."""
        result = MagicMock()
        result.fetchall.return_value = [("test_comic", 0.87)]

        session = AsyncMock()
        session.execute.return_value = result

        class _SessionFactory:
            def __call__(self):
                return self

            async def __aenter__(self):
                return session

            async def __aexit__(self, exc_type, exc, tb):
                return False

        storage = VectorStorage(_SessionFactory())
        rows = await storage.search_similar_comics([0.3, 0.4], limit=3)

        assert rows == [("test_comic", 0.87)]
        query = str(session.execute.await_args.args[0])
        params = session.execute.await_args.args[1]
        assert ":embedding" in query
        assert ":limit" in query
        assert params == {
            "embedding": "[0.3,0.4]",
            "limit": 3,
        }


# ---------------------------------------------------------------------------
# Factory Function Tests
# ---------------------------------------------------------------------------

class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_engine(self):
        """Test create_engine returns an AsyncEngine."""
        engine = create_engine("postgresql+asyncpg://user:pass@localhost/testdb")
        assert engine is not None
        # Clean up
        import asyncio
        asyncio.get_event_loop().run_until_complete(engine.dispose())

    def test_create_session_factory(self):
        """Test create_session_factory returns a session maker."""
        engine = create_engine("postgresql+asyncpg://user:pass@localhost/testdb")
        factory = create_session_factory(engine)
        assert factory is not None
        # Clean up
        import asyncio
        asyncio.get_event_loop().run_until_complete(engine.dispose())


# ---------------------------------------------------------------------------
# ORM Model Tests
# ---------------------------------------------------------------------------

class TestORMModels:
    """Tests for SQLAlchemy ORM models."""

    @pytest.mark.asyncio
    async def test_comic_model_creation(self, session_factory):
        """Test creating a ComicModel."""
        async with session_factory() as session:
            async with session.begin():
                comic = ComicModel(
                    base_fp="test_comic",
                    creator_id="creator_1",
                    work_id="work_1",
                )
                session.add(comic)

            await session.refresh(comic)
            assert comic.base_fp == "test_comic"
            assert comic.creator_id == "creator_1"
            assert comic.hit_count == 0

    @pytest.mark.asyncio
    async def test_block_model_with_comic(self, session_factory):
        """Test creating a BlockModel linked to a ComicModel."""
        async with session_factory() as session:
            async with session.begin():
                comic = ComicModel(base_fp="test_comic")
                session.add(comic)
                block = BlockModel(
                    block_uid="test_comic:1:0:0",
                    base_fp="test_comic",
                    block_type="dialogue",
                    bbox=[0, 0, 10, 10],
                    original_texts=[{"text": "test"}],
                    translations={},
                    nsfw_flag=False,
                )
                session.add(block)

            result = await session.execute(
                BlockModel.__table__.select().where(
                    BlockModel.block_uid == "test_comic:1:0:0"
                )
            )
            row = result.first()
            assert row is not None
            assert row.base_fp == "test_comic"

    @pytest.mark.asyncio
    async def test_cascade_delete(self, session_factory):
        """Test that deleting a comic cascades to blocks."""
        async with session_factory() as session:
            async with session.begin():
                comic = ComicModel(base_fp="test_comic")
                session.add(comic)
                block = BlockModel(
                    block_uid="test_comic:1:0:0",
                    base_fp="test_comic",
                    block_type="dialogue",
                    bbox=[0, 0, 10, 10],
                    original_texts=[],
                    translations={},
                    nsfw_flag=False,
                )
                session.add(block)

            # Delete comic
            async with session.begin():
                comic = await session.get(ComicModel, "test_comic")
                await session.delete(comic)

            # Block should be deleted too
            result = await session.execute(
                BlockModel.__table__.select().where(
                    BlockModel.block_uid == "test_comic:1:0:0"
                )
            )
            assert result.first() is None
