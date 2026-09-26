from fastapi import Query
from pydantic import BaseModel


class PaginationParams(BaseModel):
    skip: int
    limit: int


def pagination_params(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Max records to return (1-100)"),
) -> PaginationParams:
    return PaginationParams(skip=skip, limit=limit)
