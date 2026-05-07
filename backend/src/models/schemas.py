from pydantic import BaseModel, Field
from typing import Optional


class ChatRequest(BaseModel):
    question: str = Field(..., description="用户问题")
    session_id: Optional[str] = Field(None, description="会话ID")
    user_id: Optional[str] = Field(None, description="用户ID，用于跨会话长期记忆")
    top_k: int = Field(5, description="检索数量")


class SourceDoc(BaseModel):
    content: str = Field(..., description="文档内容")
    source: str = Field(..., description="文档来源")
    score: Optional[float] = Field(None, description="相似度分数")


class ChatResponse(BaseModel):
    answer: str = Field(..., description="AI回答")
    sources: list[SourceDoc] = Field(default_factory=list, description="参考文档")
    session_id: str = Field(..., description="会话ID")


class IngestRequest(BaseModel):
    collection_name: str = Field("customer_service_kb", description="集合名称")


class IngestResponse(BaseModel):
    status: str
    documents_loaded: int
    chunks_created: int
    collection_name: str


class HealthResponse(BaseModel):
    status: str
    milvus_connected: bool
    version: str
