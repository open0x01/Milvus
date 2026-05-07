import sqlite3
import json
import time
import numpy as np
from pathlib import Path
from typing import Any, Callable, Optional
from dataclasses import dataclass
from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class StoreValue:
    value: dict
    key: str
    namespace: tuple
    created_at: float
    updated_at: float


class SQLiteStore:
    def __init__(
        self,
        db_path: str = None,
        index: dict = None,
    ):
        self._db_path = Path(db_path or settings.SESSION_DB_PATH)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._embed_fn: Optional[Callable] = None
        self._embed_dims: int = 0
        
        if index and "embed" in index:
            self._embed_fn = index["embed"]
            self._embed_dims = index.get("dims", 1024)
        
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self):
        conn = self._get_conn()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS long_term_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    namespace TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    embedding BLOB,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    UNIQUE(namespace, key)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memory_namespace
                ON long_term_memory(namespace)
            """)
            conn.commit()
        finally:
            conn.close()

    def _namespace_to_str(self, namespace: tuple) -> str:
        return "/".join(str(n) for n in namespace)

    def _str_to_namespace(self, ns_str: str) -> tuple:
        return tuple(ns_str.split("/")) if ns_str else ()

    def put(
        self,
        namespace: tuple,
        key: str,
        value: dict,
    ) -> None:
        ns_str = self._namespace_to_str(namespace)
        value_json = json.dumps(value, ensure_ascii=False)
        now = time.time()
        
        embedding_blob = None
        if self._embed_fn and value:
            try:
                text = self._extract_text(value)
                if text:
                    embeddings = self._embed_fn([text])
                    if embeddings:
                        embedding_blob = np.array(embeddings[0], dtype=np.float32).tobytes()
            except Exception as e:
                logger.warning(f"Failed to generate embedding: {e}")

        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT INTO long_term_memory (namespace, key, value, embedding, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(namespace, key) DO UPDATE SET
                    value = excluded.value,
                    embedding = excluded.embedding,
                    updated_at = excluded.updated_at
            """, (ns_str, key, value_json, embedding_blob, now, now))
            conn.commit()
            logger.debug(f"Stored memory: namespace={ns_str}, key={key}")
        finally:
            conn.close()

    def get(self, namespace: tuple, key: str) -> Optional[StoreValue]:
        ns_str = self._namespace_to_str(namespace)
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT key, namespace, value, created_at, updated_at FROM long_term_memory WHERE namespace = ? AND key = ?",
                (ns_str, key),
            ).fetchone()
            if row:
                return StoreValue(
                    key=row["key"],
                    namespace=self._str_to_namespace(row["namespace"]),
                    value=json.loads(row["value"]),
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
            return None
        finally:
            conn.close()

    def search(
        self,
        namespace: tuple,
        *,
        filter: dict = None,
        query: str = None,
        limit: int = 10,
    ) -> list[StoreValue]:
        ns_str = self._namespace_to_str(namespace)
        conn = self._get_conn()
        try:
            if query and self._embed_fn:
                results = self._vector_search(conn, ns_str, query, limit)
            else:
                results = self._keyword_search(conn, ns_str, filter, limit)
            return results
        finally:
            conn.close()

    def _vector_search(
        self,
        conn: sqlite3.Connection,
        ns_str: str,
        query: str,
        limit: int,
    ) -> list[StoreValue]:
        try:
            query_embeddings = self._embed_fn([query])
            if not query_embeddings:
                return self._keyword_search(conn, ns_str, None, limit)
            
            query_vec = np.array(query_embeddings[0], dtype=np.float32)
            
            rows = conn.execute(
                "SELECT key, namespace, value, embedding, created_at, updated_at FROM long_term_memory WHERE namespace = ? AND embedding IS NOT NULL",
                (ns_str,),
            ).fetchall()
            
            if not rows:
                return self._keyword_search(conn, ns_str, None, limit)
            
            scored = []
            for row in rows:
                try:
                    emb = np.frombuffer(row["embedding"], dtype=np.float32)
                    similarity = np.dot(query_vec, emb) / (np.linalg.norm(query_vec) * np.linalg.norm(emb) + 1e-8)
                    scored.append((similarity, row))
                except Exception:
                    continue
            
            scored.sort(key=lambda x: x[0], reverse=True)
            results = []
            for _, row in scored[:limit]:
                results.append(StoreValue(
                    key=row["key"],
                    namespace=self._str_to_namespace(row["namespace"]),
                    value=json.loads(row["value"]),
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                ))
            return results
        except Exception as e:
            logger.warning(f"Vector search failed: {e}")
            return self._keyword_search(conn, ns_str, None, limit)

    def _keyword_search(
        self,
        conn: sqlite3.Connection,
        ns_str: str,
        filter: dict,
        limit: int,
    ) -> list[StoreValue]:
        sql = "SELECT key, namespace, value, created_at, updated_at FROM long_term_memory WHERE namespace = ?"
        params = [ns_str]
        
        if filter:
            for k, v in filter.items():
                sql += f" AND json_extract(value, '$.{k}') = ?"
                params.append(json.dumps(v) if not isinstance(v, str) else v)
        
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        
        rows = conn.execute(sql, params).fetchall()
        return [
            StoreValue(
                key=row["key"],
                namespace=self._str_to_namespace(row["namespace"]),
                value=json.loads(row["value"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    def delete(self, namespace: tuple, key: str) -> None:
        ns_str = self._namespace_to_str(namespace)
        conn = self._get_conn()
        try:
            conn.execute(
                "DELETE FROM long_term_memory WHERE namespace = ? AND key = ?",
                (ns_str, key),
            )
            conn.commit()
        finally:
            conn.close()

    def delete_namespace(self, namespace: tuple) -> None:
        ns_str = self._namespace_to_str(namespace)
        conn = self._get_conn()
        try:
            conn.execute(
                "DELETE FROM long_term_memory WHERE namespace = ?",
                (ns_str,),
            )
            conn.commit()
        finally:
            conn.close()

    def _extract_text(self, value: dict) -> str:
        texts = []
        for v in value.values():
            if isinstance(v, str):
                texts.append(v)
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, str):
                        texts.append(item)
        return " ".join(texts)


def create_memory_store() -> SQLiteStore:
    from src.core.embeddings import embedding_service
    
    def embed_texts(texts: list[str]) -> list[list[float]]:
        results = []
        for text in texts:
            emb = embedding_service.embed_query(text)
            if emb and "dense" in emb:
                results.append(emb["dense"])
            else:
                results.append([0.0] * settings.EMBEDDING_DIM)
        return results
    
    return SQLiteStore(
        db_path=settings.SESSION_DB_PATH,
        index={
            "embed": embed_texts,
            "dims": settings.EMBEDDING_DIM,
        }
    )


memory_store = create_memory_store()
