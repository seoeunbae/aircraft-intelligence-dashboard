import uuid
import json
import asyncio
from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

router = APIRouter()

_session_service = InMemorySessionService()
_runner: Runner | None = None

_APP_NAME = "aircraft_app"
_USER_ID = "user"


def get_runner() -> Runner:
    global _runner
    if _runner is None:
        from agent import root_agent
        _runner = Runner(
            agent=root_agent,
            app_name=_APP_NAME,
            session_service=_session_service,
        )
    return _runner


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    session_id: str
    response: str
    chart_data: Optional[dict] = None
    suggested_questions: Optional[list[str]] = None
    search_rows: Optional[list[dict]] = None
    search_query: Optional[str] = None


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request):
    runner = get_runner()
    session_id = req.session_id or str(uuid.uuid4())

    existing = await _session_service.get_session(
        app_name=_APP_NAME, user_id=_USER_ID, session_id=session_id
    )
    if existing is None:
        await _session_service.create_session(
            app_name=_APP_NAME, user_id=_USER_ID, session_id=session_id
        )

    user_message = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=req.message)],
    )

    response_text = ""
    async for event in runner.run_async(
        user_id=_USER_ID,
        session_id=session_id,
        new_message=user_message,
    ):
        if event.is_final_response() and event.content and event.content.parts:
            response_text = "".join(
                p.text for p in event.content.parts if hasattr(p, "text") and p.text
            )

    if not response_text:
        response_text = "응답을 생성하지 못했습니다. 다시 시도해 주세요."

    text, cd_raw, sd_raw, sq_raw = _peel_markers(response_text)

    chart_data = _parse_json(cd_raw)
    suggested_questions = _parse_json(sq_raw)

    search_rows = None
    search_query = None
    if sd_raw:
        meta = _parse_json(sd_raw)
        if meta and (kw := meta.get("keyword", "").strip()):
            search_query = kw
            datastore = request.app.state.datastore
            search_rows = await asyncio.to_thread(datastore.search, kw, 100)

    return ChatResponse(
        session_id=session_id,
        response=text,
        chart_data=chart_data,
        suggested_questions=suggested_questions,
        search_rows=search_rows,
        search_query=search_query,
    )


def _peel_markers(text: str) -> tuple[str, str | None, str | None, str | None]:
    """Strip SUGGESTED_QUESTIONS / SEARCH_DATA / CHART_DATA markers from the tail."""
    sq_raw = sd_raw = cd_raw = None

    if "SUGGESTED_QUESTIONS:" in text:
        text, sq_raw = text.rsplit("SUGGESTED_QUESTIONS:", 1)
        sq_raw = sq_raw.strip().split("\n")[0]
        text = text.rstrip()

    if "SEARCH_DATA:" in text:
        text, sd_raw = text.rsplit("SEARCH_DATA:", 1)
        sd_raw = sd_raw.strip().split("\n")[0]
        text = text.rstrip()

    if "CHART_DATA:" in text:
        text, cd_raw = text.rsplit("CHART_DATA:", 1)
        cd_raw = cd_raw.strip().split("\n")[0]
        text = text.rstrip()

    return text.strip(), cd_raw, sd_raw, sq_raw


def _parse_json(raw: str | None) -> dict | list | None:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None
