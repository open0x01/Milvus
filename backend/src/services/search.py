from langchain_openai import ChatOpenAI
from pymilvus import MilvusClient
from rank_bm25 import BM25Okapi
import numpy as np
from typing import AsyncGenerator
from src.core.embeddings import embedding_service
from src.core.config import settings
from src.core.logger import get_logger
from src.models.schemas import SourceDoc

logger = get_logger(__name__)


class SearchService:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_API_BASE,
            temperature=0
        )
        self.vector_store = None
        self._milvus_client = None
        self._bm25_cache = {}

    def _get_milvus_client(self) -> MilvusClient:
        if self._milvus_client is None:
            self._milvus_client = MilvusClient(uri=settings.MILVUS_URI)
        return self._milvus_client

    def get_vector_store(self):
        if self.vector_store is None:
            self.vector_store = Milvus(
                embedding_function=embedding_service.embeddings,
                connection_args={"uri": settings.MILVUS_URI},
                collection_name=settings.DEFAULT_COLLECTION
            )
        return self.vector_store

    def _get_text_field(self, collection_name: str) -> str:
        client = self._get_milvus_client()
        info = client.describe_collection(collection_name)
        field_names = [f["name"] for f in info["fields"]]
        if "text" in field_names:
            return "text"
        if "content" in field_names:
            return "content"
        if "chunk_text" in field_names:
            return "chunk_text"
        return "text"

    def _get_vector_field(self, collection_name: str) -> str:
        client = self._get_milvus_client()
        info = client.describe_collection(collection_name)
        field_names = [f["name"] for f in info["fields"]]
        if "dense_vector" in field_names:
            return "dense_vector"
        if "vector" in field_names:
            return "vector"
        for f in info["fields"]:
            if f["type"] in (101, 100):
                return f["name"]
        return "vector"

    def _get_metric_type(self, collection_name: str) -> str:
        client = self._get_milvus_client()
        vector_field = self._get_vector_field(collection_name)
        indexes = client.list_indexes(collection_name)
        for idx_name in indexes:
            idx_info = client.describe_index(collection_name, idx_name)
            if idx_info.get("field_name") == vector_field:
                metric = idx_info.get("metric_type", "")
                if metric:
                    return metric
        for idx_name in indexes:
            idx_info = client.describe_index(collection_name, idx_name)
            metric = idx_info.get("metric_type", "")
            if metric:
                return metric
        return "COSINE"

    def _get_pk_field(self, collection_name: str) -> str:
        client = self._get_milvus_client()
        info = client.describe_collection(collection_name)
        for f in info["fields"]:
            if f.get("is_primary", False):
                return f["name"]
        return "id"

    def _get_bm25_index(self, collection_name: str):
        if collection_name in self._bm25_cache:
            return self._bm25_cache[collection_name]

        client = self._get_milvus_client()
        text_field = self._get_text_field(collection_name)
        pk_field = self._get_pk_field(collection_name)
        docs = client.query(
            collection_name=collection_name,
            output_fields=[text_field],
            limit=10000
        )

        if not docs:
            return None, None, []

        contents = [doc[text_field] for doc in docs]
        doc_ids = [doc[pk_field] for doc in docs]

        tokenized_corpus = [text.split() for text in contents]
        bm25 = BM25Okapi(tokenized_corpus)

        self._bm25_cache[collection_name] = (bm25, doc_ids, docs)
        return bm25, doc_ids, docs

    def _hybrid_search(self, query: str, collection_name: str, top_k: int = 20, k: int = 60) -> list[SourceDoc]:
        client = self._get_milvus_client()
        text_field = self._get_text_field(collection_name)
        vector_field = self._get_vector_field(collection_name)
        metric_type = self._get_metric_type(collection_name)

        query_embedding = embedding_service.embed_query(query)
        dense_vector = query_embedding["dense"]

        dense_results = client.search(
            collection_name=collection_name,
            data=[dense_vector],
            limit=top_k,
            anns_field=vector_field,
            search_params={
                "metric_type": metric_type,
                "params": {"ef": 128},
            },
            output_fields=[text_field, "source"]
        )

        bm25, doc_ids, bm25_docs = self._get_bm25_index(collection_name)
        if bm25 is None:
            return self._dense_to_sources(dense_results[0], text_field)

        query_tokens = query.split()
        bm25_scores = bm25.get_scores(query_tokens)

        bm25_top_indices = np.argsort(bm25_scores)[::-1][:top_k]
        bm25_results = [
            (doc_ids[idx], bm25_scores[idx])
            for idx in bm25_top_indices
            if bm25_scores[idx] > 0
        ]

        dense_rank_map = {hit["id"]: rank for rank, hit in enumerate(dense_results[0])}
        bm25_rank_map = {doc_id: rank for rank, (doc_id, _) in enumerate(bm25_results)}

        all_doc_ids = set(dense_rank_map.keys()) | set(bm25_rank_map.keys())

        rrf_scores = {}
        for doc_id in all_doc_ids:
            dense_rank = dense_rank_map.get(doc_id, top_k)
            bm25_rank = bm25_rank_map.get(doc_id, len(bm25_results))
            rrf_scores[doc_id] = 1 / (k + dense_rank) + 1 / (k + bm25_rank)

        sorted_doc_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)[:top_k]

        pk_field = self._get_pk_field(collection_name)

        doc_map = {doc[pk_field]: doc for doc in bm25_docs}

        sources = []
        for rank, doc_id in enumerate(sorted_doc_ids):
            doc = doc_map.get(doc_id)
            if doc:
                sources.append(SourceDoc(
                    content=doc.get(text_field, ""),
                    source=doc.get("source", "unknown"),
                    score=round(rrf_scores[doc_id], 4)
                ))

        return sources

    def _dense_to_sources(self, dense_results: list, text_field: str = "text") -> list[SourceDoc]:
        sources = []
        for hit in dense_results:
            entity = hit.get("entity", hit)
            sources.append(SourceDoc(
                content=entity.get(text_field, entity.get("content", "")),
                source=entity.get("source", "unknown"),
                score=round(hit.get("distance", 0), 4)
            ))
        return sources

    def similarity_search(self, query: str, top_k: int = None, hybrid: bool = True) -> list[SourceDoc]:
        if top_k is None:
            top_k = settings.TOP_K

        collection = settings.DEFAULT_COLLECTION

        try:
            client = self._get_milvus_client()
            if not client.has_collection(collection):
                logger.warning(f"Collection '{collection}' does not exist, skipping search")
                return []
        except Exception as e:
            logger.warning(f"Failed to check collection existence: {e}")
            return []

        try:
            if hybrid:
                return self._hybrid_search(query, collection, top_k)
            else:
                vector_store = self.get_vector_store()
                docs = vector_store.similarity_search_with_score(query, k=top_k)
                sources = []
                for doc, score in docs:
                    sources.append(SourceDoc(
                        content=doc.page_content,
                        source=doc.metadata.get("source", "unknown"),
                        score=round(score, 4)
                    ))
                return sources
        except Exception as e:
            logger.warning(f"Search failed for collection '{collection}': {e}")
            return []


class ChatService:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_API_BASE,
            temperature=0,
            streaming=True
        )
        self.search_service = SearchService()

    def chat(self, question: str, chat_history: list[dict] = None, top_k: int = None, session_id: str = None, user_id: str = None):
        if chat_history is None:
            chat_history = []

        docs = self.search_service.similarity_search(question, top_k or settings.TOP_K)

        context = "\n\n".join([doc.content for doc in docs])

        from src.services.memory_service import memory_service
        memory_context = memory_service.build_memory_context(session_id, chat_history, user_id=user_id)

        prompt = self._get_prompt().invoke({
            "context": context,
            "chat_history": memory_context,
            "question": question
        })

        response = self.llm.invoke(prompt)

        sources = []
        for doc in docs:
            sources.append(SourceDoc(
                content=doc.content,
                source=doc.source,
                score=doc.score
            ))

        return {
            "answer": response.content if hasattr(response, 'content') else str(response),
            "sources": sources
        }

    async def chat_stream(self, question: str, chat_history: list[dict] = None, top_k: int = None, session_id: str = None, user_id: str = None) -> AsyncGenerator[dict, None]:
        if chat_history is None:
            chat_history = []

        docs = self.search_service.similarity_search(question, top_k or settings.TOP_K)

        context = "\n\n".join([doc.content for doc in docs])

        from src.services.memory_service import memory_service
        memory_context = memory_service.build_memory_context(session_id, chat_history, user_id=user_id)

        prompt_value = self._get_prompt().invoke({
            "context": context,
            "chat_history": memory_context,
            "question": question
        })

        sources = [
            SourceDoc(content=doc.content, source=doc.source, score=doc.score)
            for doc in docs
        ]

        yield {
            "type": "sources",
            "sources": [s.model_dump() for s in sources]
        }

        full_answer = ""
        async for chunk in self.llm.astream(prompt_value):
            token = chunk.content if hasattr(chunk, 'content') else str(chunk)
            if token:
                full_answer += token
                yield {
                    "type": "token",
                    "content": token
                }

        yield {
            "type": "done",
            "answer": full_answer
        }

    def _get_prompt(self):
        from langchain_core.prompts import ChatPromptTemplate

        template = """你是一个专业的漏洞安全智能客服助手。请根据提供的漏洞参考文档和对话记忆回答用户关于安全漏洞的问题。

参考文档:
{context}

对话记忆:
{chat_history}

当前问题: {question}

请遵循以下规则:
1. 只根据提供的参考文档回答，不要编造信息
2. 如果参考文档中没有相关信息，请明确告知用户
3. 回答要准确、专业、友好
4. 充分利用对话记忆中的历史信息，保持对话的连贯性和上下文理解
5. 如果用户追问之前讨论过的漏洞，请结合记忆中的信息继续深入回答
6. 回答漏洞相关问题时，请包含：漏洞名称、影响产品、漏洞类型、危险等级、CVSS评分、漏洞描述、修复建议等信息
7. 如果用户询问某个产品的漏洞，请列出相关的所有漏洞

回答:"""

        return ChatPromptTemplate.from_template(template)


search_service = SearchService()
chat_service = ChatService()
