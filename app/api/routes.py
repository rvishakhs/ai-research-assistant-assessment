from fastapi import APIRouter, HTTPException, Request

from app.schemas.api import QueryRequest, QueryResponse

router = APIRouter()

@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}

@router.post("/query", response_model=QueryResponse)
async def query(request: Request, body: QueryRequest) -> QueryResponse:
    runner = request.app.state.runner
    try:
        result = await runner.run_query(body.query, body.researcher_id)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return QueryResponse(**result)