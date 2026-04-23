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

    chart_data = None
    if "CHART_DATA:" in response_text:
        parts = response_text.split("CHART_DATA:", 1)
        response_text = parts[0].strip()
        remainder = parts[1].strip()
        # SUGGESTED_QUESTIONS may follow CHART_DATA on a new line
        if "SUGGESTED_QUESTIONS:" in remainder:
            chart_part, sq_part = remainder.split("SUGGESTED_QUESTIONS:", 1)
            remainder = chart_part.strip()
            suggested_raw = sq_part.strip()
        else:
            suggested_raw = None
        try:
            chart_data = json.loads(remainder)
        except Exception:
            pass
    else:
        suggested_raw = None

    suggested_questions = None
    if "SUGGESTED_QUESTIONS:" in response_text:
        parts = response_text.split("SUGGESTED_QUESTIONS:", 1)
        response_text = parts[0].strip()
        suggested_raw = parts[1].strip()
    if suggested_raw:
        try:
            suggested_questions = json.loads(suggested_raw)
        except Exception:
            pass

    return ChatResponse(
        session_id=session_id,
        response=response_text,
        chart_data=chart_data,
        suggested_questions=suggested_questions,
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
async def data_search(q: Optional[str] = None, limit: int = 100):
    """Full-text search across all columns. Returns overall statistics when q is omitted."""
    if not q or not q.strip():
        try:
            stats_sql = f"""
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
            rows = await asyncio.to_thread(run_query, stats_sql)
            summary = rows[0] if rows else {}
            cleaned = {
                k: (str(v) if not isinstance(v, (int, float, bool, str, type(None))) else v)
                for k, v in summary.items()
            }
            return {"summary": cleaned, "query": None}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    kw = q.strip().replace("'", "\\'")
    try:
        sql = f"""
        SELECT *
        FROM {FULL_TABLE}
        WHERE
          SEARCH(MALFUNCTION, '{kw}')
          OR SEARCH(CORRECTIVE_ACTION, '{kw}')
          OR SEARCH(NR_WORKORDER_NAME, '{kw}')
          OR LOWER(AC_TYPE)  LIKE LOWER('%{kw}%')
          OR LOWER(AC_NO)    LIKE LOWER('%{kw}%')
          OR LOWER(AMP)      LIKE LOWER('%{kw}%')
          OR LOWER(ATA_CODE) LIKE LOWER('%{kw}%')
          OR LOWER(MSG_NO)   LIKE LOWER('%{kw}%')
          OR EXISTS (
              SELECT 1
              FROM UNNEST(SPLIT(COALESCE(COMPONENT_KEYWORD, ''), ',')) AS _kw
              WHERE TRIM(LOWER(_kw)) LIKE LOWER('%{kw}%')
          )
        LIMIT {limit}
        """
        rows = await asyncio.to_thread(run_query, sql)
        cleaned = [
            {k: (str(v) if not isinstance(v, (int, float, bool, str, type(None))) else v)
             for k, v in row.items()}
            for row in rows
        ]
        return {"rows": cleaned, "total": len(cleaned), "query": q}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Static files & SPA fallback ───────────────────────────────────────────────
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
async def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))
