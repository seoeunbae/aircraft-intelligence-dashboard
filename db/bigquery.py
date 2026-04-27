import json
from google.cloud import bigquery
from google import genai as _genai

from config import Settings
from .base import DataStore


class BigQueryDataStore(DataStore):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: bigquery.Client | None = None

    @property
    def _bq(self) -> bigquery.Client:
        if self._client is None:
            self._client = bigquery.Client(
                project=self._settings.project_id,
                location=self._settings.location,
            )
        return self._client

    @property
    def _table(self) -> str:
        return self._settings.full_table_ref

    def _run(self, sql: str) -> list[dict]:
        return [dict(row) for row in self._bq.query(sql).result()]

    def get_summary(self) -> dict:
        rows = self._run(f"""
            SELECT
                COUNT(*)                  AS total_records,
                COUNT(DISTINCT AC_NO)     AS total_aircraft,
                COUNT(DISTINCT AC_TYPE)   AS aircraft_types,
                COUNT(DISTINCT AMP)       AS operators,
                COUNT(DISTINCT ATA_CODE)  AS ata_codes,
                MIN(NR_REQUEST_DATE)      AS earliest_date,
                MAX(NR_REQUEST_DATE)      AS latest_date
            FROM {self._table}
        """)
        return rows[0] if rows else {}

    def get_charts(self) -> dict:
        return {
            "aircraft_type": self._run(f"""
                SELECT COALESCE(AC_TYPE, 'Unknown') AS label, COUNT(*) AS value
                FROM {self._table} GROUP BY 1 ORDER BY 2 DESC LIMIT 10
            """),
            "operator": self._run(f"""
                SELECT COALESCE(AMP, 'Unknown') AS label, COUNT(*) AS value
                FROM {self._table} GROUP BY 1 ORDER BY 2 DESC LIMIT 10
            """),
            "ata_code": self._run(f"""
                SELECT COALESCE(ATA_CODE, 'Unknown') AS label, COUNT(*) AS value
                FROM {self._table} GROUP BY 1 ORDER BY 2 DESC LIMIT 10
            """),
            "component_keyword": self._run(f"""
                SELECT UPPER(TRIM(kw)) AS label, COUNT(*) AS value
                FROM {self._table},
                     UNNEST(SPLIT(COALESCE(COMPONENT_KEYWORD, ''), ',')) AS kw
                WHERE TRIM(kw) != ''
                GROUP BY 1 ORDER BY 2 DESC LIMIT 10
            """),
        }

    def get_table(self, limit: int, offset: int) -> list[dict]:
        rows = self._run(f"""
            SELECT * FROM {self._table}
            ORDER BY 1 LIMIT {limit} OFFSET {offset}
        """)
        return [_serialize(row) for row in rows]

    def search(self, keyword: str, limit: int = 100) -> list[dict]:
        keywords = _extract_aviation_keywords(keyword)
        seen: dict[str, dict] = {}
        per_limit = max(limit // max(len(keywords), 1), 20)

        for kw in keywords:
            escaped = kw.strip().replace("'", "\\'")
            if not escaped:
                continue
            rows = self._run(f"""
                SELECT * FROM {self._table}
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
            """)
            for row in rows:
                row = _serialize(row)
                key = row.get("ID") or row.get("NR_NUMBER") or str(row)
                seen.setdefault(key, row)

        return list(seen.values())[:limit]


def _serialize(row: dict) -> dict:
    return {
        k: (str(v) if not isinstance(v, (int, float, bool, str, type(None))) else v)
        for k, v in row.items()
    }


def _extract_aviation_keywords(sentence: str) -> list[str]:
    """Use Gemini to extract aviation maintenance keywords from free-form input."""
    prompt = (
        "Extract aviation/aircraft maintenance related english keywords from the following text.\n"
        "Return ONLY a JSON array of strings, no explanation, no markdown fences.\n"
        "Focus on: component names (APU, engine, hydraulic pump, etc.), ATA codes, "
        "aircraft types (B737, A320), malfunction types, operator codes.\n"
        "Limit to the most relevant terms (max 5).\n"
        "If the input is already a single short keyword, return it as-is in the array.\n\n"
        f"Input: {sentence}"
    )
    try:
        client = _genai.Client()
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        text = response.text.strip()
        if "```" in text:
            text = text.split("```")[1].lstrip("json").strip()
        keywords = json.loads(text)
        cleaned = [k.strip() for k in keywords if isinstance(k, str) and k.strip()]
        return cleaned if cleaned else [sentence]
    except Exception:
        return [sentence]
