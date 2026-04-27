import asyncio
from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


def _store(request: Request):
    return request.app.state.datastore


@router.get("/data/summary")
async def data_summary(request: Request):
    try:
        return await asyncio.to_thread(_store(request).get_summary)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/data/charts")
async def data_charts(request: Request):
    try:
        return await asyncio.to_thread(_store(request).get_charts)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/data/table")
async def data_table(request: Request, limit: int = 50, offset: int = 0):
    try:
        rows = await asyncio.to_thread(_store(request).get_table, limit, offset)
        return {"rows": rows, "limit": limit, "offset": offset}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/data/search")
async def data_search(request: Request, q: str, limit: int = 100):
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required")
    try:
        rows = await asyncio.to_thread(_store(request).search, q, limit)
        return {"rows": rows, "total": len(rows), "query": q}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
