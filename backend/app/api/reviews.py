"""Start, read, and cancel a local review. The model cannot change files."""

from fastapi import APIRouter, HTTPException, Request

from app.schemas.review import ReviewDetail, ReviewStart
from app.services.review import ReviewRejected

router = APIRouter(tags=["reviews"])


@router.post("/reviews", response_model=ReviewDetail, status_code=201)
def start_review(body: ReviewStart, request: Request) -> ReviewDetail:
    service = request.app.state.review_service
    try:
        review_id = service.start(body.project_id, body.base_ref, body.paths)
        return service.detail(review_id)
    except ReviewRejected as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/reviews/{review_id}", response_model=ReviewDetail)
def get_review(review_id: str, request: Request) -> ReviewDetail:
    try:
        return request.app.state.review_service.detail(review_id)
    except ReviewRejected as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/reviews/{review_id}/cancel", response_model=ReviewDetail)
def cancel_review(review_id: str, request: Request) -> ReviewDetail:
    service = request.app.state.review_service
    try:
        service.cancel(review_id)
        return service.detail(review_id)
    except ReviewRejected as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
