import math
from typing import Generic, TypeVar, List
from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Standardized API envelope for paginated dataset responses.
    Prevents memory exhaustion and unindexed full-table retrieval.
    """
    items: List[T]
    total: int = Field(..., description="Total count of matching records")
    page: int = Field(..., ge=1, description="Current 1-indexed page")
    page_size: int = Field(..., ge=1, le=100, description="Page size limit")
    total_pages: int = Field(..., description="Total available pages")
    has_next: bool = Field(..., description="Whether subsequent pages exist")
    has_previous: bool = Field(..., description="Whether preceding pages exist")

    @classmethod
    def create(cls, items: List[T], total: int, page: int, page_size: int):
        total_pages = math.ceil(total / page_size) if total > 0 else 1
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1,
        )
