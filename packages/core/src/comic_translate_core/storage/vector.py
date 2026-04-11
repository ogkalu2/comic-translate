"""Vector storage for pgvector-based similarity search."""

from __future__ import annotations

from typing import List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .postgres import BlockModel, ComicModel


class VectorStorage:
    """Vector similarity search using pgvector.

    Provides methods for storing and searching embeddings using
    cosine similarity via PostgreSQL's pgvector extension.

    Example:
        >>> from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        >>> engine = create_async_engine("postgresql+asyncpg://user:pass@localhost/comicdb")
        >>> factory = async_sessionmaker(engine, expire_on_commit=False)
        >>> vstore = VectorStorage(factory)
        >>> results = await vstore.search_similar_blocks([0.1, 0.2, ...], limit=5)
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory

    @staticmethod
    def _vector_literal(embedding: List[float]) -> str:
        """Serialize an embedding to pgvector's text input format."""
        return "[" + ",".join(f"{value:g}" for value in embedding) + "]"

    async def store_embedding(self, block_uid: str, embedding: List[float]) -> None:
        """Store or update an embedding for a block.

        Args:
            block_uid: The block identifier.
            embedding: The embedding vector (must be 384-dimensional).
        """
        async with self._session_factory() as session:
            async with session.begin():
                block = await session.get(BlockModel, block_uid)
                if block is None:
                    raise FileNotFoundError(f"No block found with uid: {block_uid}")
                block.embedding = embedding

    async def store_comic_embedding(self, base_fp: str, embedding: List[float]) -> None:
        """Store or update a meta embedding for a comic.

        Args:
            base_fp: The comic fingerprint identifier.
            embedding: The embedding vector (must be 384-dimensional).
        """
        async with self._session_factory() as session:
            async with session.begin():
                comic = await session.get(ComicModel, base_fp)
                if comic is None:
                    raise FileNotFoundError(f"No comic found with base_fp: {base_fp}")
                comic.meta_embedding = embedding

    async def search_similar_blocks(
        self,
        embedding: List[float],
        limit: int = 10,
        base_fp: Optional[str] = None,
    ) -> List[Tuple[str, float]]:
        """Search for blocks with similar embeddings using cosine similarity.

        Args:
            embedding: The query embedding vector.
            limit: Maximum number of results to return.
            base_fp: Optional filter to search within a specific comic.

        Returns:
            List of (block_uid, similarity_score) tuples, ordered by
            descending similarity. Scores range from -1 to 1 (higher is more similar).
        """
        async with self._session_factory() as session:
            query = """
                SELECT block_uid, 1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
                FROM blocks
                WHERE embedding IS NOT NULL
            """
            params = {
                "embedding": self._vector_literal(embedding),
                "limit": limit,
            }

            if base_fp:
                query += " AND base_fp = :base_fp"
                params["base_fp"] = base_fp

            query += " ORDER BY embedding <=> CAST(:embedding AS vector) LIMIT :limit"

            result = await session.execute(text(query), params)
            rows = result.fetchall()
            return [(row[0], float(row[1])) for row in rows]

    async def search_similar_comics(
        self,
        embedding: List[float],
        limit: int = 10,
    ) -> List[Tuple[str, float]]:
        """Search for comics with similar meta embeddings.

        Args:
            embedding: The query embedding vector.
            limit: Maximum number of results to return.

        Returns:
            List of (base_fp, similarity_score) tuples.
        """
        async with self._session_factory() as session:
            query = """
                SELECT base_fp, 1 - (meta_embedding <=> CAST(:embedding AS vector)) AS similarity
                FROM comics
                WHERE meta_embedding IS NOT NULL
                ORDER BY meta_embedding <=> CAST(:embedding AS vector)
                LIMIT :limit
            """
            result = await session.execute(
                text(query),
                {
                    "embedding": self._vector_literal(embedding),
                    "limit": limit,
                },
            )
            rows = result.fetchall()
            return [(row[0], float(row[1])) for row in rows]

    async def get_embedding(self, block_uid: str) -> Optional[List[float]]:
        """Retrieve the embedding for a specific block.

        Args:
            block_uid: The block identifier.

        Returns:
            The embedding vector, or None if not found.
        """
        async with self._session_factory() as session:
            block = await session.get(BlockModel, block_uid)
            if block is None:
                return None
            return block.embedding
