from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from src.models.schemas import ChatRequest, ChatResponse, SourceDoc
from src.services.search import chat_service, search_service
from src.services.session_store import session_store
from src.services.memory_service import memory_service
from src.core.logger import get_logger
import uuid
import json
import asyncio

router = APIRouter(prefix="/chat", tags=["chat"])
logger = get_logger(__name__)


def _handle_memory_task(task: asyncio.Task):
    if task.cancelled():
        return
    exc = task.exception()
    if exc:
        logger.error(f"Memory update task failed: {exc}", exc_info=exc)


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    try:
        session_id = request.session_id
        is_new_session = session_id is None
        if is_new_session:
            session_id = str(uuid.uuid4())

        session_store.create_session(session_id)

        if is_new_session:
            title = request.question[:30] + ("..." if len(request.question) > 30 else "")
            session_store.update_title(session_id, title)

        chat_history = session_store.get_history(session_id)
        session_store.add_message(session_id, "user", request.question)

        async def event_generator():
            full_answer = ""
            try:
                async for chunk in chat_service.chat_stream(
                    question=request.question,
                    chat_history=chat_history,
                    top_k=request.top_k,
                    session_id=session_id,
                    user_id=request.user_id
                ):
                    if chunk["type"] == "sources":
                        data = json.dumps({
                            "type": "sources",
                            "sources": chunk["sources"],
                            "session_id": session_id
                        }, ensure_ascii=False)
                        yield f"data: {data}\n\n"

                    elif chunk["type"] == "token":
                        full_answer += chunk["content"]
                        data = json.dumps({
                            "type": "token",
                            "content": chunk["content"]
                        }, ensure_ascii=False)
                        yield f"data: {data}\n\n"

                    elif chunk["type"] == "done":
                        session_store.add_message(session_id, "assistant", chunk["answer"])

                        updated_history = session_store.get_history(session_id)
                        task = asyncio.create_task(
                            memory_service.update_memory(session_id, updated_history, user_id=request.user_id)
                        )
                        task.add_done_callback(_handle_memory_task)

                        data = json.dumps({
                            "type": "done",
                            "answer": chunk["answer"],
                            "session_id": session_id
                        }, ensure_ascii=False)
                        yield f"data: {data}\n\n"

            except Exception as e:
                error_data = json.dumps({
                    "type": "error",
                    "content": str(e)
                }, ensure_ascii=False)
                yield f"data: {error_data}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        session_id = request.session_id
        is_new_session = session_id is None
        if is_new_session:
            session_id = str(uuid.uuid4())

        session_store.create_session(session_id)

        if is_new_session:
            title = request.question[:30] + ("..." if len(request.question) > 30 else "")
            session_store.update_title(session_id, title)

        chat_history = session_store.get_history(session_id)

        result = chat_service.chat(
            question=request.question,
            chat_history=chat_history,
            top_k=request.top_k,
            session_id=session_id
        )

        session_store.add_message(session_id, "user", request.question)
        session_store.add_message(session_id, "assistant", result["answer"])

        updated_history = session_store.get_history(session_id)
        task = asyncio.create_task(
            memory_service.update_memory(session_id, updated_history)
        )
        task.add_done_callback(_handle_memory_task)

        return ChatResponse(
            answer=result["answer"],
            sources=[SourceDoc(**s.model_dump()) for s in result["sources"]],
            session_id=session_id
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions")
async def list_sessions():
    sessions = session_store.list_sessions()
    return {"sessions": sessions}


@router.get("/history/{session_id}")
async def get_chat_history(session_id: str):
    history = session_store.get_history(session_id)
    return {"session_id": session_id, "history": history}


@router.delete("/history/{session_id}")
async def delete_chat_history(session_id: str):
    session_store.delete_session(session_id)
    memory_service.delete_memory(session_id)
    return {"status": "deleted", "session_id": session_id}
