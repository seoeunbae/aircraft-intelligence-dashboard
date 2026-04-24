"""
FastAPI backend for Aircraft Intelligence Dashboard
Endpoints:
  POST /api/chat          – send a message to the ADK agent
  GET  /api/data/summary  – fleet summary counts from BigQuery
  GET  /api/data/charts   – chart data (status, type, route distributions)
  GET  /api/data/table    – paginated raw table rows
"""

import os
import uuid
import json
import asyncio
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "cloud-cycle-pj")
DATASET_ID = os.getenv("BIGQUERY_DATASET", "mdas-dataset")
TABLE_ID   = os.getenv("BIGQUERY_TABLE", "aircraft_dummy")
LOCATION   = os.getenv("BIGQUERY_REGION", os.getenv("GOOGLE_CLOUD_LOCATION", "asia-southeast1"))

# ── BigQuery client ───────────────────────────────────────────────────────────
from google.cloud import bigquery

bq_client: bigquery.Client = None

def get_bq_client() -> bigquery.Client:
    global bq_client
    if bq_client is None:
        bq_client = bigquery.Client(project=PROJECT_ID, location=LOCATION)
    return bq_client

def run_query(sql: str) -> list[dict]:
    client = get_bq_client()
    rows = client.query(sql).result()
    return [dict(row) for row in rows]

FULL_TABLE = f"`{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}`"

def _extract_aviation_keywords(sentence: str) -> list[str]:
    """Gemini를 이용해 문장에서 항공 정비 관련 키워드를 추출한다."""
    import json
    from google import genai as _genai

    client = _genai.Client()
    prompt = (
        "Extract aviation/aircraft maintenance related english keywords from the following text.\n"
        "Return ONLY a JSON array of strings, no explanation, no markdown fences.\n"
        "Focus on: component names (APU, engine, hydraulic pump, etc.), ATA , "
        "aircraft types (B737, A320), malfunction types, operator codes.\n"
        "Limit to the most relevant terms (max 5).\n"
        "If the input is already a single short keyword, return it as-is in the array.\n\n"
        f"Input: {sentence}"
    )
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        text = response.text.strip()
        if "```" in text:
            text = text.split("```")[1].lstrip("json").strip()
        keywords = json.loads(text)
        cleaned = [k.strip() for k in keywords if isinstance(k, str) and k.strip()]
        return cleaned if cleaned else [sentence]

    except Exception:
        return [sentence]


def _search_sync(kw: str, limit: int = 100) -> list[dict]:
    keywords = _extract_aviation_keywords(kw)

    seen: dict[str, dict] = {}
    per_limit = max(limit // max(len(keywords), 1), 20)

    for keyword in keywords:
        escaped = keyword.strip().replace("'", "\\'")
        if not escaped:
            continue
        sql = f"""
        SELECT *
        FROM {FULL_TABLE}
        WHERE
          SEARCH(MALFUNCTION, '{escaped}')
          OR SEARCH(CORRECTIVE_ACTION, '{escaped}')
          OR SEARCH(NR_WORKORDER_NAME, '{escaped}')
          OR LOWER(AC_TYPE)  LIKE LOWER('%{escaped}%')
          OR LOWER(AC_NO)    LIKE LOWER('%{escaped}%')
          OR LOWER(AMP)      LIKE LOWER('%{escaped}%')
          OR LOWER(ATA_CODE) LIKE LOWER('%{escaped}%')
          OR LOWER(MSG_NO)   LIKE LOWER('%{escaped}%')
          OR EXISTS (
              SELECT 1
              FROM UNNEST(SPLIT(COALESCE(COMPONENT_KEYWORD, ''), ',')) AS _kw
              WHERE TRIM(LOWER(_kw)) LIKE LOWER('%{escaped}%')
          )
        LIMIT {per_limit}
        """
        rows = run_query(sql)
        for row in rows:
            serialized = {
                k: (str(v) if not isinstance(v, (int, float, bool, str, type(None))) else v)
                for k, v in row.items()
            }
            key = serialized.get("ID") or serialized.get("NR_NUMBER") or str(serialized)
            if key not in seen:
                seen[key] = serialized

    results = list(seen.values())[:limit]
    return results

# ── ADK agent session management ─────────────────────────────────────────────
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.genai import types as genai_types

_session_service = InMemorySessionService()
_runner: Runner = None

def get_runner() -> Runner:
    global _runner
    if _runner is None:
        from agent import root_agent
        _runner = Runner(
            agent=root_agent,
            app_name="aircraft_app",
            session_service=_session_service,
        )
    return _runner

# ── FastAPI app ───────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm up runner and BQ client at startup
    get_runner()
    get_bq_client()
    yield

app = FastAPI(title="Aircraft Intelligence Dashboard", lifespan=lifespan)

# ── Request / Response models ─────────────────────────────────────────────────
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

# ── Chat endpoint ─────────────────────────────────────────────────────────────
@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    runner = get_runner()
    session_id = req.session_id or str(uuid.uuid4())

    # Ensure session exists
    existing = await _session_service.get_session(
        app_name="aircraft_app", user_id="user", session_id=session_id
    )
    if existing is None:
        await _session_service.create_session(
            app_name="aircraft_app", user_id="user", session_id=session_id
        )

    user_message = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=req.message)],
    )

    response_text = ""
    async for event in runner.run_async(
        user_id="user",
        session_id=session_id,
        new_message=user_message,
    ):
        if event.is_final_response() and event.content and event.content.parts:
            response_text = "".join(
                p.text for p in event.content.parts if hasattr(p, "text") and p.text
            )

    if not response_text:
        response_text = "응답을 생성하지 못했습니다. 다시 시도해 주세요."

    # Peel special markers from the end of the response (order: SQ → SD → CD)
    text = response_text

    sq_raw = sd_raw = cd_raw = None
    if "SUGGESTED_QUESTIONS:" in text:
        text, sq_raw = text.rsplit("SUGGESTED_QUESTIONS:", 1)
        text = text.rstrip()
        sq_raw = sq_raw.strip().split("\n")[0]

    if "SEARCH_DATA:" in text:
        text, sd_raw = text.rsplit("SEARCH_DATA:", 1)
        text = text.rstrip()
        sd_raw = sd_raw.strip().split("\n")[0]

    if "CHART_DATA:" in text:
        text, cd_raw = text.rsplit("CHART_DATA:", 1)
        text = text.rstrip()
        cd_raw = cd_raw.strip().split("\n")[0]

    response_text = text.strip()

    chart_data = None
    if cd_raw:
        try:
            chart_data = json.loads(cd_raw)
        except Exception:
            pass

    search_rows = None
    search_query = None
    if sd_raw:
        try:
            meta = json.loads(sd_raw)
            kw = meta.get("keyword", "").strip()
            if kw:
                search_query = kw
                search_rows = await asyncio.to_thread(_search_sync, kw, 100)
        except Exception:
            pass

    suggested_questions = None
    if sq_raw:
        try:
            suggested_questions = json.loads(sq_raw)
        except Exception:
            pass
    return ChatResponse(
        session_id=session_id,
        response=response_text,
        chart_data=chart_data,
        suggested_questions=suggested_questions,
        search_rows=search_rows,
        search_query=search_query,
    )


# ── Dashboard data endpoints ──────────────────────────────────────────────────
@app.get("/api/data/summary")
async def data_summary():
    """Return high-level KPI counts for the maintenance records."""
    try:
        sql = f"""
        SELECT
            COUNT(*)                  AS total_records,
            COUNT(DISTINCT AC_NO)     AS total_aircraft,
            COUNT(DISTINCT AC_TYPE)   AS aircraft_types,
            COUNT(DISTINCT AMP)       AS operators,
            COUNT(DISTINCT ATA_CODE)  AS ata_codes,
            MIN(NR_REQUEST_DATE)      AS earliest_date,
            MAX(NR_REQUEST_DATE)      AS latest_date
        FROM {FULL_TABLE}
        """
        rows = run_query(sql)
        return rows[0] if rows else {}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/data/charts")
async def data_charts():
    """Return data for all dashboard charts."""
    try:
        type_sql = f"""
        SELECT
            COALESCE(AC_TYPE, 'Unknown') AS label,
            COUNT(*) AS value
        FROM {FULL_TABLE}
        GROUP BY label
        ORDER BY value DESC
        LIMIT 10
        """

        operator_sql = f"""
        SELECT
            COALESCE(AMP, 'Unknown') AS label,
            COUNT(*) AS value
        FROM {FULL_TABLE}
        GROUP BY label
        ORDER BY value DESC
        LIMIT 10
        """

        ata_sql = f"""
        SELECT
            COALESCE(ATA_CODE, 'Unknown') AS label,
            COUNT(*) AS value
        FROM {FULL_TABLE}
        GROUP BY label
        ORDER BY value DESC
        LIMIT 10
        """

        keyword_sql = f"""
        SELECT
            UPPER(TRIM(kw)) AS label,
            COUNT(*) AS value
        FROM {FULL_TABLE},
             UNNEST(SPLIT(COALESCE(COMPONENT_KEYWORD, ''), ',')) AS kw
        WHERE TRIM(kw) != ''
        GROUP BY label
        ORDER BY value DESC
        LIMIT 10
        """

        type_data, operator_data, ata_data, keyword_data = await asyncio.gather(
            asyncio.to_thread(run_query, type_sql),
            asyncio.to_thread(run_query, operator_sql),
            asyncio.to_thread(run_query, ata_sql),
            asyncio.to_thread(run_query, keyword_sql),
        )

        return {
            "aircraft_type": type_data,
            "operator": operator_data,
            "ata_code": ata_data,
            "component_keyword": keyword_data,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/data/table")
async def data_table(limit: int = 50, offset: int = 0):
    """Return paginated rows from the aircraft table."""
    try:
        sql = f"""
        SELECT *
        FROM {FULL_TABLE}
        ORDER BY 1
        LIMIT {limit}
        OFFSET {offset}
        """
        rows = run_query(sql)
        # Convert any non-serialisable types (dates, decimals) to strings
        cleaned = [
            {k: (str(v) if not isinstance(v, (int, float, bool, str, type(None))) else v)
             for k, v in row.items()}
            for row in rows
        ]
        return {"rows": cleaned, "limit": limit, "offset": offset}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/data/search")
async def data_search(q: str, limit: int = 100):
    """Full-text search across all columns."""
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required")
    try:
        rows = await asyncio.to_thread(_search_sync, q, limit)
        return {"rows": rows, "total": len(rows), "query": q}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Static files & SPA fallback ───────────────────────────────────────────────
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
async def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))
