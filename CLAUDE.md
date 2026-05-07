# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

漏洞智能客服 — A RAG-based vulnerability intelligence Q&A system using Milvus vector database, LangChain, and LLM. Supports hybrid search (dense vector + BM25 sparse), multi-format data ingestion, and conversational retrieval with session memory.

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Frontend  │────▶│   Backend   │────▶│   Milvus    │
│   (React)   │◀────│  (FastAPI)  │◀────│  (VectorDB) │
└─────────────┘     └─────────────┘     └─────────────┘
                          │
                    ┌─────┴─────┐
                    ▼           ▼
              ┌──────────┐ ┌──────────┐
              │ Ollama   │ │  LLM API │
              │(Embedding)│ │(MiniMax)│
              └──────────┘ └──────────┘
```

- **Frontend**: React 19 + TypeScript + Tailwind + Zustand
- **Backend**: FastAPI + LangChain, routes in `src/api/routers/`
- **Vector Store**: Milvus 2.5 (HNSW index, COSINE metric)
- **Embeddings**: Ollama (default, `qwen3-embedding:0.6b-q8_0`) or local model
- **LLM**: Configurable (default MiniMax via OpenAI-compatible API)
- **Session Storage**: SQLite (`data/sessions.db`)

## Commands

### Backend Development
```bash
cd backend

# Install dependencies (uses uv)
uv sync

# Run development server with hot reload
uv run uvicorn src.api.main:app --reload --port 8000

# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/test_file.py -v
```

### Frontend Development
```bash
cd frontend
npm install
npm run dev
```

### Data Ingestion
```bash
cd backend

# Generic document ingestion (pdf, docx, txt, xml, json, md, sqlite)
python scripts/ingest_data.py --path ./data/docs --collection my_kb

# Plugin-specific ingestion with dense + sparse dual vectors
python scripts/ingest_plugins.py --path ./data/plugins.xml --collection vuln_kb

# Custom chunking parameters
python scripts/ingest_data.py --path ./data/docs --collection kb --chunk-size 512 --chunk-overlap 100
```

### Docker Compose (Full Stack)
```bash
docker-compose up -d
# Access at http://localhost
```

## Key Backend Modules

| Module | Purpose |
|--------|---------|
| `src/core/config.py` | Settings via Pydantic — Milvus URI, LLM API keys, model names, collection names |
| `src/core/embeddings.py` | `embedding_service` — wraps Ollama embedding API |
| `src/core/vector_store.py` | `vector_store_service` — Milvus connection and health checks |
| `src/core/prompt.py` | Chat prompt template for vulnerability Q&A |
| `src/services/search.py` | `SearchService` (hybrid BM25 + dense RRF search) + `ChatService` (LLM chain) |
| `src/services/ingest.py` | `IngestService` — document loading, chunking, Milvus ingestion |
| `src/services/session_store.py` | SQLite-based session persistence |
| `src/services/sqlite_store.py` | `memory_store` — key-value store for long-term memory (summary, facts, preferences) |
| `src/services/memory_service.py` | `memory_service` — LLM-powered conversation summarization and fact extraction |
| `src/api/routers/chat.py` | `/api/chat` endpoint with streaming support and session memory |
| `src/api/routers/ingest.py` | `/api/ingest` endpoint for file uploads |
| `src/models/schemas.py` | Pydantic models: `SourceDoc`, `ChatRequest`, `ChatResponse`, `HealthResponse` |

## Search Architecture

`SearchService` performs **hybrid search**:
1. **Dense vector search** — queries Milvus HNSW index
2. **BM25 sparse search** — in-memory `rank_bm25.BM25Okapi` on corpus
3. **RRF fusion** — `score = 1/(k + dense_rank) + 1/(k + bm25_rank)` with `k=60`

The `_hybrid_search` method auto-detects collection schema (text field, vector field, metric type, primary key).

## Memory Architecture

`MemoryService` provides long-term conversation memory:
1. **Summary** — LLM-generated conversation summary (when `MEMORY_SUMMARY_ENABLED=true`)
2. **Facts** — Extracted key-value pairs (user name, vulnerabilities discussed, products mentioned)
3. **Preferences** — User preference list
4. **Recent window** — Last N messages for immediate context

Memory is persisted via `sqlite_store.py` (a key-value store backed by SQLite).

## Vector Store Schema

- `vuln_kb` (default): single `vector` field (1024-dim), HNSW index, COSINE metric
- `plugins` collection: separate `dense_vector` and `sparse_vector` fields for hybrid search

Auto-detection logic in `SearchService._get_*` methods handles varying schemas.

## Environment Variables

Key variables in `.env`:
- `MILVUS_URI` — Milvus server URI (default: `http://milvus:19530`)
- `OPENAI_API_KEY` / `OPENAI_API_BASE` — LLM API credentials
- `OPENAI_MODEL` — LLM model name (default: `MiniMax-M2.7`)
- `OLLAMA_BASE_URL` — Ollama server (default: `http://localhost:11434`)
- `OLLAMA_EMBEDDING_MODEL` — Ollama embedding model (default: `qwen3-embedding:0.6b-q8_0`)
- `DEFAULT_COLLECTION` — Default Milvus collection (default: `vuln_kb`)
- `TOP_K` — Retrieval return count (default: `5`)
- `SESSION_DB_PATH` — SQLite session storage path (default: `data/sessions.db`)
- `SESSION_MAX_HISTORY` — Max chat history messages per session (default: `100`)
- `MEMORY_WINDOW_SIZE` — Window for recent messages in memory context (default: `4`)
- `MEMORY_SUMMARY_ENABLED` — Enable LLM-generated conversation summary (default: `true`)

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chat` | POST | Send message, returns answer + sources (supports streaming) |
| `/api/chat/history/{session_id}` | GET | Get session chat history |
| `/api/ingest` | POST | Upload document (multipart) |
| `/api/health` | GET | Health check with Milvus connection status |

## Data Ingestion Formats

`ingest_data.py` auto-detects format by extension:
- `.pdf` / `.docx` / `.txt` — document loaders
- `.xml` — if contains `<RECORD>` with `pluginid` → plugins format; otherwise FAQ format
- `.json` — structured JSON
- `.md` — Markdown (split by headings/paragraphs)
- `.db` / `.sqlite` / `.sqlite3` — SQLite database tables

`ingest_plugins.py` is specialized for plugin XML with dense + sparse vector generation.

## Frontend Structure

```
frontend/src/
├── api/          # API client functions
├── components/   # React components
├── stores/       # Zustand state stores
├── App.tsx       # Main app component
└── main.tsx      # Entry point
```
