from pydantic import BaseModel, Field
from typing import Optional
from app.modules.chatbot.llm.client import chat_completion_structured
from app.modules.chatbot.llm.prompt_loader import load_prompt

class SqlQuery(BaseModel):
    name: str = Field(..., description="Tên query")
    sql: str = Field(..., description="Câu lệnh SQL")
    purpose: str = Field(..., description="Mục đích")

class Citation(BaseModel):
    source_type: str = Field(...)
    ticker: Optional[str] = None
    metric: Optional[str] = None
    period: Optional[str] = None

class SqlQueries(BaseModel):
    thought: str = Field(..., description="Giải thích chiến lược")
    queries: list[SqlQuery] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)


async def generate_analysis_sql(
    message: str,
    entities: dict,
    rag_context: list[dict],
    ind_code_matches: list[dict],
) -> dict:
    system_prompt = load_prompt("analysis_sql_agent.txt")

    prompt = f"""Câu hỏi user:
{message}

Entities:
{json.dumps(entities, ensure_ascii=False)}

BCTC ind_code candidates:
{json.dumps(ind_code_matches, ensure_ascii=False)}

Schema/RAG context:
{json.dumps(rag_context, ensure_ascii=False)}

Hãy sinh danh sách SQL phục vụ phân tích.
"""
    try:
        response = await chat_completion_structured(
            user_prompt=prompt,
            system_prompt=system_prompt,
            response_format=SqlQueries,
            temperature=0.0,
            max_tokens=3000,
        )
        return response.model_dump()
    except Exception:
        return {
            "thought": "Fallback error",
            "queries": [],
            "citations": []
        }