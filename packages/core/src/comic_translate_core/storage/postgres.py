"""PostgreSQL storage backend with pgvector support using SQLAlchemy ORM."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    String, Integer, Boolean, Text, JSON, DateTime, ForeignKey, func, select, delete
)
from sqlalchemy.ext.asyncio import (
    AsyncSession, async_sessionmaker, create_async_engine, AsyncEngine
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from ..interfaces.storage import IScriptStorage
from ..models import ScriptExport, QAPatchSet, ScriptBlock, BlockContext, BlockType, QAPatch
from ..models.block_v2 import (
    Block, BlockType as BlockTypeV2, OriginalText, TranslationVersion, TranslationHistory, SemanticRouting
)


# ---------------------------------------------------------------------------
# ORM Base & Models
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""
    pass


class ComicModel(Base):
    """ORM model for comics table."""
    __tablename__ = "comics"

    base_fp: Mapped[str] = mapped_column(String, primary_key=True)
    creator_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    work_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    meta_embedding: Mapped[Optional[list]] = mapped_column(Vector(384), nullable=True)
    hit_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    blocks: Mapped[List["BlockModel"]] = relationship(back_populates="comic", cascade="all, delete-orphan")
    contributions: Mapped[List["ContributionModel"]] = relationship(back_populates="comic", cascade="all, delete-orphan")


class BlockModel(Base):
    """ORM model for blocks table."""
    __tablename__ = "blocks"

    block_uid: Mapped[str] = mapped_column(String, primary_key=True)
    base_fp: Mapped[str] = mapped_column(String, ForeignKey("comics.base_fp", ondelete="CASCADE"), nullable=False)
    block_type: Mapped[str] = mapped_column(String, nullable=False)
    bbox: Mapped[dict] = mapped_column(JSON, nullable=False)
    original_texts: Mapped[dict] = mapped_column(JSON, nullable=False)
    translations: Mapped[dict] = mapped_column(JSON, default=dict)
    semantic_routing: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    nsfw_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    embedding: Mapped[Optional[list]] = mapped_column(Vector(384), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    comic: Mapped["ComicModel"] = relationship(back_populates="blocks")


class ContributionModel(Base):
    """ORM model for contributions table."""
    __tablename__ = "contributions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_key: Mapped[str] = mapped_column(String, nullable=False)
    base_fp: Mapped[str] = mapped_column(String, ForeignKey("comics.base_fp", ondelete="CASCADE"), nullable=False)
    block_uid: Mapped[Optional[str]] = mapped_column(String, ForeignKey("blocks.block_uid", ondelete="CASCADE"), nullable=True)
    manual_edits: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    comic: Mapped["ComicModel"] = relationship(back_populates="contributions")


# ---------------------------------------------------------------------------
# Database Engine & Session Factory
# ---------------------------------------------------------------------------

def create_engine(database_url: str, **kwargs) -> AsyncEngine:
    """Create an async SQLAlchemy engine for PostgreSQL.

    Args:
        database_url: PostgreSQL connection string.
            Example: "postgresql+asyncpg://user:pass@localhost:5432/comicdb"
        **kwargs: Additional engine options.

    Returns:
        AsyncEngine instance.
    """
    return create_async_engine(database_url, **kwargs)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory.

    Args:
        engine: AsyncEngine instance.

    Returns:
        Session factory for creating AsyncSession instances.
    """
    return async_sessionmaker(engine, expire_on_commit=False)


# ---------------------------------------------------------------------------
# PostgresStorage - IScriptStorage implementation
# ---------------------------------------------------------------------------

class PostgresStorage(IScriptStorage):
    """PostgreSQL-backed storage implementing IScriptStorage.

    Uses SQLAlchemy ORM with pgvector for vector operations.

    Example:
        >>> engine = create_engine("postgresql+asyncpg://user:pass@localhost/comicdb")
        >>> factory = create_session_factory(engine)
        >>> storage = PostgresStorage(factory)
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory

    async def init_schema(self) -> None:
        """Create all tables if they don't exist.

        Call this once at application startup.
        """
        async with self._session_factory() as session:
            async with session.bind.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

    # -- IScriptStorage interface -------------------------------------------

    def save_script(self, script: ScriptExport, path: str) -> None:
        """Save a ScriptExport to PostgreSQL.

        The `path` parameter is used as the base_fp key.
        """
        import asyncio
        asyncio.get_event_loop().run_until_complete(self._save_script_async(script, path))

    def load_script(self, path: str) -> ScriptExport:
        """Load a ScriptExport from PostgreSQL by base_fp."""
        import asyncio
        return asyncio.get_event_loop().run_until_complete(self._load_script_async(path))

    def save_patch(self, patch_set: QAPatchSet, path: str) -> None:
        """Save a QAPatchSet to PostgreSQL."""
        import asyncio
        asyncio.get_event_loop().run_until_complete(self._save_patch_async(patch_set, path))

    def load_patch(self, path: str) -> QAPatchSet:
        """Load a QAPatchSet from PostgreSQL by base_fp."""
        import asyncio
        return asyncio.get_event_loop().run_until_complete(self._load_patch_async(path))

    # -- Async implementations ---------------------------------------------

    async def _save_script_async(self, script: ScriptExport, base_fp: str) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                # Upsert comic
                comic = await session.get(ComicModel, base_fp)
                if comic is None:
                    comic = ComicModel(base_fp=base_fp)
                    session.add(comic)
                comic.hit_count = (comic.hit_count or 0) + 1
                comic.updated_at = datetime.utcnow()

                # Delete existing blocks for this comic
                await session.execute(
                    delete(BlockModel).where(BlockModel.base_fp == base_fp)
                )

                # Insert blocks
                for block in script.blocks:
                    block_model = BlockModel(
                        block_uid=f"{base_fp}:{block.page}:{block.block_id}",
                        base_fp=base_fp,
                        block_type=block.type.value,
                        bbox=block.bbox,
                        original_texts=[{
                            "variant_id": "default",
                            "lang": script.source_lang,
                            "text": block.original,
                        }],
                        translations={"default": block.translated} if block.translated else {},
                        semantic_routing={
                            "speaker": block.context.speaker if block.context else None,
                            "prev_block": block.context.prev_block if block.context else None,
                            "next_block": block.context.next_block if block.context else None,
                        } if block.context else None,
                        nsfw_flag=False,
                    )
                    session.add(block_model)

    async def _load_script_async(self, base_fp: str) -> ScriptExport:
        async with self._session_factory() as session:
            comic = await session.get(ComicModel, base_fp)
            if comic is None:
                raise FileNotFoundError(f"No comic found with base_fp: {base_fp}")

            result = await session.execute(
                select(BlockModel).where(BlockModel.base_fp == base_fp)
            )
            block_models = result.scalars().all()

            blocks: List[ScriptBlock] = []
            for bm in block_models:
                original_texts = bm.original_texts or []
                original_text = original_texts[0]["text"] if original_texts else ""
                translations = bm.translations or {}
                translated = translations.get("default", "")

                ctx_data = bm.semantic_routing or {}
                context = BlockContext(
                    speaker=ctx_data.get("speaker"),
                    prev_block=ctx_data.get("prev_block"),
                    next_block=ctx_data.get("next_block"),
                )

                # Extract page and block_id from block_uid
                parts = bm.block_uid.split(":")
                page = int(parts[1]) if len(parts) > 1 else 0
                block_id = parts[2] if len(parts) > 2 else "0"

                blocks.append(ScriptBlock(
                    block_id=block_id,
                    page=page,
                    type=BlockType(bm.block_type),
                    bbox=bm.bbox,
                    original=original_text,
                    translated=translated,
                    original_variant="",
                    context=context,
                    qa_metadata=None,
                ))

            return ScriptExport(
                version="2.0",
                comic_id=base_fp,
                base_fp=base_fp,
                script_id=base_fp,
                source_lang="",
                target_lang="",
                exported_at=comic.updated_at.timestamp() if comic.updated_at else 0.0,
                page_range=[],
                active_variant="",
                variants={},
                glossary_snapshot={},
                blocks=blocks,
            )

    async def _save_patch_async(self, patch_set: QAPatchSet, base_fp: str) -> None:
        """Save patches as contributions."""
        async with self._session_factory() as session:
            async with session.begin():
                # Ensure comic exists
                comic = await session.get(ComicModel, base_fp)
                if comic is None:
                    comic = ComicModel(base_fp=base_fp)
                    session.add(comic)

                for patch in patch_set.patches:
                    contribution = ContributionModel(
                        user_key="system",
                        base_fp=base_fp,
                        block_uid=patch.block_id,
                        manual_edits={
                            "category": patch.category.value if patch.category else None,
                            "block_id": patch.block_id,
                            "original": patch.original,
                            "old_translated": patch.old_translated,
                            "new_translated": patch.new_translated,
                            "reason": patch.reason,
                            "confidence": patch.confidence,
                        },
                        approved=False,
                    )
                    session.add(contribution)

    async def _load_patch_async(self, base_fp: str) -> QAPatchSet:
        """Load patches from contributions."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(ContributionModel)
                .where(ContributionModel.base_fp == base_fp)
                .order_by(ContributionModel.created_at)
            )
            contributions = result.scalars().all()

            patches: List[QAPatch] = []
            for c in contributions:
                edits = c.manual_edits or {}
                from ..models import PatchCategory
                category_str = edits.get("category")
                category = PatchCategory(category_str) if category_str else PatchCategory.GRAMMAR
                patches.append(QAPatch(
                    block_id=edits.get("block_id", ""),
                    original=edits.get("original", ""),
                    old_translated=edits.get("old_translated", ""),
                    new_translated=edits.get("new_translated", ""),
                    reason=edits.get("reason", ""),
                    category=category,
                    confidence=edits.get("confidence", 1.0),
                ))

            return QAPatchSet(
                version="1.0",
                comic_id=base_fp,
                base_fp=base_fp,
                created_at=0.0,
                qa_model="postgres",
                chunk_range={},
                summary={},
                patches=patches,
            )

    # -- Block-level async methods -----------------------------------------

    async def save_block_async(self, block: Block) -> None:
        """Save a Block v2 model to PostgreSQL."""
        async with self._session_factory() as session:
            async with session.begin():
                base_fp = block.block_uid.split(":")[0]

                # Ensure comic exists
                comic = await session.get(ComicModel, base_fp)
                if comic is None:
                    comic = ComicModel(base_fp=base_fp)
                    session.add(comic)

                # Upsert block
                existing = await session.get(BlockModel, block.block_uid)
                if existing:
                    bm = existing
                else:
                    bm = BlockModel(block_uid=block.block_uid, base_fp=base_fp)
                    session.add(bm)

                bm.block_type = block.type.value
                bm.bbox = block.bbox
                bm.original_texts = [
                    {"variant_id": ot.variant_id, "lang": ot.lang, "text": ot.text}
                    for ot in block.original_texts
                ]
                bm.translations = {
                    lang: {
                        ver: {
                            "text": tv.text,
                            "status": tv.status,
                            "weight": tv.weight,
                            "history": [
                                {"action": h.action, "source": h.source, "timestamp": h.timestamp}
                                for h in tv.history
                            ],
                            "source": tv.source,
                        }
                        for ver, tv in versions.items()
                    }
                    for lang, versions in block.translations.items()
                }
                bm.semantic_routing = {
                    "ner_entities": block.semantic_routing.ner_entities,
                    "sfx_detected": block.semantic_routing.sfx_detected,
                    "route": block.semantic_routing.route,
                } if block.semantic_routing else None
                bm.nsfw_flag = block.nsfw_flag
                bm.embedding = block.embedding
                bm.updated_at = datetime.utcnow()

    async def load_block_async(self, block_uid: str) -> Block:
        """Load a Block v2 model from PostgreSQL."""
        async with self._session_factory() as session:
            bm = await session.get(BlockModel, block_uid)
            if bm is None:
                raise FileNotFoundError(f"No block found with uid: {block_uid}")
            return self._block_model_to_block(bm)

    async def list_blocks_async(self, base_fp: str) -> List[str]:
        """List all block UIDs for a given base_fp."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(BlockModel.block_uid).where(BlockModel.base_fp == base_fp)
            )
            return [row[0] for row in result.all()]

    @staticmethod
    def _block_model_to_block(bm: BlockModel) -> Block:
        """Convert BlockModel ORM object to Block dataclass."""
        original_texts = [
            OriginalText(
                variant_id=ot.get("variant_id", ""),
                lang=ot.get("lang", ""),
                text=ot.get("text", ""),
            )
            for ot in (bm.original_texts or [])
        ]

        translations: Dict[str, Dict[str, TranslationVersion]] = {}
        for lang, versions in (bm.translations or {}).items():
            translations[lang] = {}
            for ver, tv in versions.items():
                translations[lang][ver] = TranslationVersion(
                    text=tv.get("text", ""),
                    status=tv.get("status", "pending_review"),
                    weight=tv.get("weight", 1.0),
                    history=[
                        TranslationHistory(
                            action=h.get("action", ""),
                            source=h.get("source", ""),
                            timestamp=h.get("timestamp"),
                        )
                        for h in tv.get("history", [])
                    ],
                    source=tv.get("source"),
                )

        sr_data = bm.semantic_routing
        semantic_routing = SemanticRouting(
            ner_entities=sr_data.get("ner_entities", []),
            sfx_detected=sr_data.get("sfx_detected", False),
            route=sr_data.get("route", ""),
        ) if sr_data else None

        return Block(
        block_uid=bm.block_uid,
        nsfw_flag=bm.nsfw_flag,
        type=BlockTypeV2(bm.block_type),
            bbox=bm.bbox,
            original_texts=original_texts,
            translations=translations,
            semantic_routing=semantic_routing,
            embedding=bm.embedding,
        )
