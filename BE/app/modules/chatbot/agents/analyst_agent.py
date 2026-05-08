import asyncio
import json
from pydantic import BaseModel, Field
from app.modules.chatbot.llm.client import chat_completion_structured
from app.modules.chatbot.llm.prompt_loader import load_prompt
from app.modules.chatbot.sql.executor import execute_sql
from app.modules.chatbot.agents.subagents.yoy_query_agent import run_yoy_query_agent
from app.modules.chatbot.agents.subagents.peer_query_agent import run_peer_query_agent
from app.modules.chatbot.agents.subagents.insight_agent import run_insight_agent


class AnalysisPlan(BaseModel):
    need_yoy: bool = Field(True, description="Cần so sánh theo thời gian không")
    need_peer: bool = Field(False, description="Cần so sánh cùng ngành không")
    yoy_focus: str = Field("", description="Trọng tâm so sánh YoY")
    peer_focus: str = Field("", description="Trọng tâm so sánh Peer")
    reasoning: str = Field("", description="Lý do")


async def _execute_queries(queries: list[dict]) -> list[dict]:
    """Thực thi danh sách query song song, bỏ qua lỗi."""
    async def _exec_one(q: dict) -> dict | None:
        try:
            rows = await execute_sql(q["sql"])
            return {
                "name": q["name"],
                "sql": q["sql"],
                "purpose": q.get("purpose", ""),
                "rows": rows,
            }
        except Exception as e:
            return {
                "name": q["name"],
                "sql": q["sql"],
                "purpose": q.get("purpose", ""),
                "rows": [],
                "error": str(e),
            }

    results = await asyncio.gather(*[_exec_one(q) for q in queries])
    return [r for r in results if r is not None]


async def run_analyst_agent(
    message: str,
    entities: dict,
    schema_context: list[dict],
    ind_code_matches: list[dict],
) -> dict:
    """
    Agent Analyst điều phối toàn bộ pipeline phân tích:

    Bước 1 — Lập kế hoạch: quyết định cần sub-agent nào
    Bước 2 — Song song:
        5.1a Sub-agent YoY Query    (nếu need_yoy)
        5.1b Sub-agent Peer Query   (nếu need_peer)
    Bước 3 — Thực thi SQL song song
    Bước 4 — Sub-agent Insight tổng hợp → bản phân tích hoàn thiện

    Returns:
        {
            "answer": str,
            "query_results": list[dict],
            "sql_used": list[str],
            "citations": list[dict],
            "thought": str,
        }
    """

    # ── Bước 1: Lập kế hoạch ─────────────────────────────────────────
    plan_system = load_prompt("agent_analyst.txt")
    plan_prompt = f"""Câu hỏi user:
{message}

Entities:
{json.dumps(entities, ensure_ascii=False)}

Hãy lập kế hoạch phân tích.
"""
    try:
        plan = await chat_completion_structured(
            user_prompt=plan_prompt,
            system_prompt=plan_system,
            response_format=AnalysisPlan,
            temperature=0.0,
            max_tokens=500,
        )
    except Exception:
        # Fallback: kích hoạt cả hai sub-agent
        plan = AnalysisPlan(
            need_yoy=True,
            need_peer=bool(entities.get("tickers")),
            yoy_focus="Phân tích xu hướng các chỉ tiêu tài chính theo quý",
            peer_focus="So sánh với các công ty cùng ngành",
            reasoning="Fallback plan"
        )

    need_yoy: bool = plan.need_yoy
    need_peer: bool = plan.need_peer
    yoy_focus: str = plan.yoy_focus
    peer_focus: str = plan.peer_focus
    thought: str = plan.reasoning

    # ── Bước 2: Chạy song song sub-agent query ───────────────────────
    async def _empty_yoy():
        return {"queries": [], "citations": [], "thought": "Không cần YoY"}

    yoy_task = (
        run_yoy_query_agent(message, entities, schema_context, ind_code_matches, yoy_focus)
        if need_yoy
        else _empty_yoy()
    )

    async def _empty_peer():
        return {"queries": [], "citations": [], "thought": "Không cần Peer"}

    peer_task = (
        run_peer_query_agent(message, entities, schema_context, ind_code_matches, peer_focus)
        if need_peer
        else _empty_peer()
    )

    yoy_payload, peer_payload = await asyncio.gather(yoy_task, peer_task)

    # Gộp toàn bộ query + citations
    all_queries: list[dict] = [
        *yoy_payload.get("queries", []),
        *peer_payload.get("queries", []),
    ]
    citations: list[dict] = [
        *yoy_payload.get("citations", []),
        *peer_payload.get("citations", []),
    ]

    # ── Bước 3: Thực thi SQL song song ───────────────────────────────
    query_results = await _execute_queries(all_queries)
    sql_used = [r["sql"] for r in query_results]

    # ── Bước 4: Insight Agent → bản phân tích hoàn thiện ─────────────
    answer = await run_insight_agent(
        user_message=message,
        query_results=query_results,
        citations=citations,
    )

    return {
        "answer": answer,
        "query_results": query_results,
        "sql_used": sql_used,
        "citations": citations,
        "thought": (
            f"**Kế hoạch:** {thought}\n\n"
            f"**YoY:** {yoy_payload.get('thought', '')}\n\n"
            f"**Peer:** {peer_payload.get('thought', '')}"
        ),
    }