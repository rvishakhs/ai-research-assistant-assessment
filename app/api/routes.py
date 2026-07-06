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
        result = await runner.run(body.question, body.researcher_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return QueryResponse(**result)
